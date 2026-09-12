from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .foundation.common import digest_value, is_sha256
from .projections import (
    DECISION_OPTIONS,
    FAIL_CLOSED_NORMALIZED_VALUE_BY_DECISION_KEY,
)


PROJECTOR_CONTRACT = "casepath.record-driven-fact-projector/1.0.0"
CATALOG_CONTRACT = "casepath.bounded-fact-catalog/1.0.0"


class RecordProjectionError(ValueError):
    """Raised when an observation cannot safely update the accepted fact roster."""


@dataclass(frozen=True, slots=True)
class FactCatalogProjection:
    facts: tuple[dict[str, Any], ...]
    catalog: tuple[dict[str, Any], ...]
    receipt: dict[str, Any]


def _pipeline_source_ref(value: Mapping[str, Any]) -> dict[str, Any]:
    artifact_id = value.get("source_id") or value.get("artifact_id")
    locator_kind = value.get("locator_kind")
    source_sha256 = value.get("source_sha256") or value.get("artifact_sha256")
    if not isinstance(artifact_id, str) or not artifact_id:
        raise RecordProjectionError("source reference requires a source identity")
    if not isinstance(source_sha256, str) or not is_sha256(source_sha256):
        raise RecordProjectionError("source reference requires a lowercase SHA-256")
    if locator_kind == "text_quote":
        page = value.get("page")
        excerpt = value.get("sanitized_excerpt", value.get("excerpt"))
        if (
            not isinstance(page, int)
            or isinstance(page, bool)
            or page < 1
            or not isinstance(excerpt, str)
            or not excerpt
        ):
            raise RecordProjectionError("text source reference is incomplete")
        return {
            "artifact_id": artifact_id,
            "locator_kind": "text_quote",
            "page": page,
            "excerpt": excerpt,
            "agent": "Record-driven Evidence Projector",
        }
    if locator_kind == "metadata_field":
        field = value.get("field")
        if not isinstance(field, str) or not field or "value" not in value:
            raise RecordProjectionError("metadata source reference is incomplete")
        return {
            "artifact_id": artifact_id,
            "locator_kind": "metadata_field",
            "field": field,
            "value": value["value"],
            "agent": "Record-driven Evidence Projector",
        }
    raise RecordProjectionError("unsupported record source locator kind")


def _validate_seed_facts(
    facts: Sequence[Mapping[str, Any]],
    *,
    decision_options: Mapping[str, Mapping[str, str]],
) -> None:
    ids: list[str] = []
    roles: list[str] = []
    for value in facts:
        fact_id = value.get("fact_id")
        if not isinstance(fact_id, str) or not fact_id:
            raise RecordProjectionError("fact IDs must be non-empty strings")
        ids.append(fact_id)
        role = value.get("semantic_role")
        if role is not None:
            if not isinstance(role, str) or not role:
                raise RecordProjectionError("semantic roles must be non-empty strings")
            roles.append(role)
        controls_process = value.get("controls_process") is True
        decision_key = value.get("decision_key")
        normalized_value = value.get("normalized_value")
        if controls_process:
            if (
                not isinstance(decision_key, str)
                or normalized_value not in decision_options.get(decision_key, {})
                or value.get("decision_value")
                != decision_options[decision_key][normalized_value]
            ):
                raise RecordProjectionError("controlling fact decision triple is invalid")
        elif any(
            item is not None
            for item in (decision_key, normalized_value, value.get("decision_value"))
        ):
            raise RecordProjectionError("non-controlling fact has a decision value")
    if len(ids) != len(set(ids)):
        raise RecordProjectionError("fact IDs must be unique")
    if len(roles) != len(set(roles)):
        raise RecordProjectionError("semantic roles must be unique")


def _apply_observation(
    fact: dict[str, Any],
    observation: Mapping[str, Any],
    *,
    decision_options: Mapping[str, Mapping[str, str]],
    fail_closed_values: Mapping[str, str],
) -> dict[str, Any]:
    evidence_status = observation.get("evidence_status")
    if evidence_status not in {
        "provided_sufficient",
        "provided_insufficient",
        "unavailable",
    }:
        raise RecordProjectionError("observation evidence_status is invalid")
    state = observation.get("fact_state")
    if state not in {"known", "unknown", "conflicting"}:
        raise RecordProjectionError("observation fact_state is invalid")
    value = observation.get("value")
    explanation = observation.get("explanation")
    if not isinstance(value, str) or not value:
        raise RecordProjectionError("observation value is required")
    if not isinstance(explanation, str) or not explanation:
        raise RecordProjectionError("observation explanation is required")
    raw_refs = observation.get("source_refs")
    if not isinstance(raw_refs, (list, tuple)) or not raw_refs:
        raise RecordProjectionError("an observation requires source provenance")
    source_refs = [_pipeline_source_ref(item) for item in raw_refs]
    if evidence_status == "unavailable":
        raise RecordProjectionError(
            "unavailable evidence must use the tool-unavailable event"
        )
    if evidence_status == "provided_insufficient":
        # Retain exact provenance for the evidence ledger without authoring the
        # fact value or route decision.  The one exception is an independently
        # admitted scoped-correction record: it may withdraw a prior assertion
        # to the fail-closed state, but it still cannot assert a new value.
        updated = deepcopy(fact)
        existing = list(updated.get("source_refs", []))
        for source_ref in source_refs:
            if source_ref not in existing:
                existing.append(source_ref)
        updated["source_refs"] = existing
        if observation.get("contract") == "casepath.correction-observation/1.0.0":
            if state != "unknown" or observation.get("normalized_value") is not None:
                raise RecordProjectionError(
                    "an insufficient correction may only withdraw to unknown"
                )
            updated.update(
                {
                    "value": value,
                    "state": "unknown",
                    "explanation": explanation,
                    "confidence": 1.0,
                }
            )
            if updated.get("controls_process") is True:
                decision_key = updated.get("decision_key")
                if not isinstance(decision_key, str):
                    raise RecordProjectionError(
                        "controlling fact decision key is invalid"
                    )
                safe_unknown = fail_closed_values.get(decision_key)
                if safe_unknown not in decision_options.get(decision_key, {}):
                    raise RecordProjectionError(
                        "controlling fact has no fail-closed state"
                    )
                updated["normalized_value"] = safe_unknown
                updated["decision_value"] = decision_options[decision_key][
                    safe_unknown
                ]
        return updated
    updated = deepcopy(fact)
    cumulative_source_refs = list(updated.get("source_refs", []))
    for source_ref in source_refs:
        if source_ref not in cumulative_source_refs:
            cumulative_source_refs.append(source_ref)
    updated.update(
        {
            "value": value,
            "state": state,
            "explanation": explanation,
            # The loop state is cumulative.  A later observation may revise the
            # decision-bearing value, but it cannot erase the immutable source
            # history that earlier evidence/checklist rows still bind.
            "source_refs": cumulative_source_refs,
            "confidence": 1.0,
        }
    )
    if updated.get("controls_process") is True and state == "known":
        decision_key = updated.get("decision_key")
        if not isinstance(decision_key, str):
            raise RecordProjectionError("controlling fact decision key is invalid")
        normalized_value = observation.get("normalized_value")
        if normalized_value not in decision_options.get(decision_key, {}):
            raise RecordProjectionError("observation decision value is inadmissible")
        updated["normalized_value"] = normalized_value
        updated["decision_value"] = decision_options[decision_key][normalized_value]
    elif updated.get("controls_process") is True:
        decision_key = updated.get("decision_key")
        if not isinstance(decision_key, str):
            raise RecordProjectionError("controlling fact decision key is invalid")
        safe_unknown = fail_closed_values.get(decision_key)
        if safe_unknown not in decision_options.get(decision_key, {}):
            raise RecordProjectionError("controlling fact has no fail-closed state")
        updated["normalized_value"] = safe_unknown
        updated["decision_value"] = decision_options[decision_key][safe_unknown]
    elif observation.get(
        "normalized_value"
    ) is not None:
        raise RecordProjectionError("non-controlling fact cannot receive a decision value")
    return updated


def build_bounded_fact_catalog_v1(
    facts: Sequence[Mapping[str, Any]],
    *,
    decision_options: Mapping[str, Mapping[str, str]] = DECISION_OPTIONS,
) -> tuple[dict[str, Any], ...]:
    _validate_seed_facts(facts, decision_options=decision_options)
    return tuple(
        {
            "fact_id": value["fact_id"],
            "label": value["label"],
            "controls_process": value["controls_process"],
            "decision_key": value["decision_key"],
            "normalized_options": decision_options.get(value["decision_key"], {}),
            "admissible_normalized_values": (
                [value["normalized_value"]] if value["controls_process"] else []
            ),
            "expected_state": value["state"],
            "canonical_value": value["value"],
            "canonical_explanation": value["explanation"],
            "semantic_role": value["semantic_role"],
            "deterministic_confidence": value["confidence"],
            "admissible_text_refs": [
                {
                    "artifact_id": source_ref["artifact_id"],
                    "page": source_ref["page"],
                    "excerpt": source_ref["excerpt"],
                }
                for source_ref in value["source_refs"]
                if source_ref["locator_kind"] == "text_quote"
            ],
            "deterministic_text_refs": [
                deepcopy(source_ref)
                for source_ref in value["source_refs"]
                if source_ref["locator_kind"] == "text_quote"
            ],
            "bounded_enrichments": [
                deepcopy(source_ref)
                for source_ref in value["source_refs"]
                if source_ref["locator_kind"]
                in {"visual_observation", "metadata_field"}
            ],
        }
        for value in facts
    )


def project_record_driven_facts_v1(
    *,
    seed_facts: Sequence[Mapping[str, Any]],
    observation_records: Sequence[Mapping[str, Any]] = (),
    decision_options: Mapping[str, Mapping[str, str]] = DECISION_OPTIONS,
    fail_closed_values: Mapping[
        str, str
    ] = FAIL_CLOSED_NORMALIZED_VALUE_BY_DECISION_KEY,
) -> FactCatalogProjection:
    """Apply trusted observation records to the fixed v20 fact roster.

    The roster remains a versioned process contract. Values, branch decisions,
    explanations, and provenance may change only through self-hashed observation
    records. The same projected facts are the sole input to both process routing
    and the bounded model catalog.
    """

    _validate_seed_facts(seed_facts, decision_options=decision_options)
    facts = [deepcopy(dict(value)) for value in seed_facts]
    by_id = {value["fact_id"]: index for index, value in enumerate(facts)}
    observation_hashes: list[str] = []
    for raw in observation_records:
        observation = dict(raw)
        claimed_hash = observation.get("observation_sha256")
        if not isinstance(claimed_hash, str) or not is_sha256(claimed_hash):
            raise RecordProjectionError("observation is not self-hashed")
        if digest_value(
            {key: value for key, value in observation.items() if key != "observation_sha256"}
        ) != claimed_hash:
            raise RecordProjectionError("observation self-hash mismatch")
        fact_id = observation.get("fact_id")
        if fact_id not in by_id:
            raise RecordProjectionError("observation references an unknown fact")
        facts[by_id[fact_id]] = _apply_observation(
            facts[by_id[fact_id]],
            observation,
            decision_options=decision_options,
            fail_closed_values=fail_closed_values,
        )
        observation_hashes.append(claimed_hash)
    _validate_seed_facts(facts, decision_options=decision_options)
    catalog = build_bounded_fact_catalog_v1(
        facts, decision_options=decision_options
    )
    payload = {
        "contract": PROJECTOR_CONTRACT,
        "catalog_contract": CATALOG_CONTRACT,
        "seed_facts_sha256": digest_value(list(seed_facts)),
        "observation_sha256s": observation_hashes,
        "facts_sha256": digest_value(facts),
        "catalog_sha256": digest_value(list(catalog)),
        "fact_count": len(facts),
    }
    return FactCatalogProjection(
        facts=tuple(facts),
        catalog=catalog,
        receipt={**payload, "receipt_sha256": digest_value(payload)},
    )


__all__ = [
    "CATALOG_CONTRACT",
    "PROJECTOR_CONTRACT",
    "FactCatalogProjection",
    "RecordProjectionError",
    "build_bounded_fact_catalog_v1",
    "project_record_driven_facts_v1",
]
