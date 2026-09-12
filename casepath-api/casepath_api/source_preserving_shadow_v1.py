from __future__ import annotations

import base64
import binascii
import json
from datetime import datetime
from hashlib import sha256
from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import Field, StrictInt, model_validator

from .foundation.common import digest_text, digest_value, is_sha256
from .foundation.contracts import FoundationModel


SHADOW_ADAPTER_ID = "casepath.source-preserving-shadow-adapter/1.0.0"
SHADOW_ROUTE = "/api/shadow/source-preserving/v1/admit"
PremiseState = Literal["T", "F", "U", "C"]
SupportPolarity = Literal["positive", "negative"]


class SourcePreservingShadowError(ValueError):
    pass


def _validate_time(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise ValueError("timestamp is invalid") from exc
    if parsed.tzinfo is None:
        raise ValueError("timestamp lacks a timezone")
    return value


class ShadowScopeV1(FoundationModel):
    actor: str | None = Field(default=None, min_length=1, max_length=200)
    object: str | None = Field(default=None, min_length=1, max_length=200)
    time: str | None = Field(default=None, min_length=1, max_length=200)
    obligation: str = Field(min_length=1, max_length=200)


class ShadowSourceV1(FoundationModel):
    contract: Literal["casepath.shadow-source/1.0.0"] = (
        "casepath.shadow-source/1.0.0"
    )
    source_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{1,127}$")
    source_version: str = Field(min_length=1, max_length=200)
    content_sha256: str
    content_b64: str = Field(min_length=1, max_length=300_000)
    decoded_text: str = Field(min_length=1, max_length=200_000)
    acquired_at: str
    acquisition_action_id: str | None = Field(default=None, max_length=128)
    allowed_premise_ids: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_source(self) -> "ShadowSourceV1":
        _validate_time(self.acquired_at)
        if not is_sha256(self.content_sha256):
            raise ValueError("source content hash is invalid")
        try:
            raw = base64.b64decode(self.content_b64, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError("source content is not canonical base64") from exc
        try:
            decoded = raw.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise ValueError("source content is not strict UTF-8") from exc
        if (
            base64.b64encode(raw).decode("ascii") != self.content_b64
            or decoded != self.decoded_text
            or sha256(raw).hexdigest() != self.content_sha256
            or len(set(self.allowed_premise_ids)) != len(self.allowed_premise_ids)
        ):
            raise ValueError("source byte, text, hash, or scope identity differs")
        return self


class ShadowSpanV1(FoundationModel):
    contract: Literal["casepath.shadow-source-span/1.0.0"] = (
        "casepath.shadow-source-span/1.0.0"
    )
    source_id: str
    source_version: str
    source_sha256: str
    text_start: StrictInt = Field(ge=0)
    text_end: StrictInt = Field(gt=0)
    byte_start: StrictInt = Field(ge=0)
    byte_end: StrictInt = Field(gt=0)
    exact_text: str = Field(min_length=1)
    span_sha256: str


class ShadowSupportBundleV1(FoundationModel):
    contract: Literal["casepath.shadow-support-bundle/1.0.0"] = (
        "casepath.shadow-support-bundle/1.0.0"
    )
    support_id: str = Field(pattern=r"^support\.[0-9a-f]{64}$")
    premise_id: str
    polarity: SupportPolarity
    spans: tuple[ShadowSpanV1, ...] = Field(min_length=1)
    scope: ShadowScopeV1
    supersedes: tuple[str, ...] = ()
    model_receipt_sha256: str
    semantic_admission: Literal["fallible_model_interpretation_exact_spans"] = (
        "fallible_model_interpretation_exact_spans"
    )


class ShadowCorrectionRelationV1(FoundationModel):
    contract: Literal["casepath.shadow-correction-relation/1.0.0"] = (
        "casepath.shadow-correction-relation/1.0.0"
    )
    correction_id: str
    premise_id: str
    target_support_ids: tuple[str, ...]
    target_source_versions: dict[str, tuple[str, ...]]
    evidence_spans: tuple[ShadowSpanV1, ...]
    scope: ShadowScopeV1 | None
    expected_parent_state_sha256: str
    status: Literal["applied", "quarantined"]
    reason: str
    correction_sha256: str


class ProposedShadowCorrectionV1(FoundationModel):
    contract: Literal["casepath.proposed-shadow-correction/1.0.0"] = (
        "casepath.proposed-shadow-correction/1.0.0"
    )
    correction_id: str = Field(pattern=r"^correction\.[A-Za-z0-9._:-]{1,120}$")
    premise_id: str
    target_support_ids: tuple[str, ...] = Field(min_length=1)
    target_source_versions: dict[str, tuple[str, ...]]
    evidence_spans: tuple[ShadowSpanV1, ...] = Field(min_length=1)
    scope: ShadowScopeV1 | None
    expected_parent_state_sha256: str


class ShadowPremiseV1(FoundationModel):
    contract: Literal["casepath.shadow-premise-state/1.0.0"] = (
        "casepath.shadow-premise-state/1.0.0"
    )
    premise_id: str
    state: PremiseState
    support_bundles: tuple[ShadowSupportBundleV1, ...] = ()
    correction_relations: tuple[ShadowCorrectionRelationV1, ...] = ()
    rationale: str = ""
    rationale_kind: Literal["model_rationale_not_source_quote"] = (
        "model_rationale_not_source_quote"
    )


class ShadowPremiseSpecV1(FoundationModel):
    premise_id: str
    statement: str = Field(min_length=1)
    scope: ShadowScopeV1
    provenance_source_ids: tuple[str, ...] = ()


class ShadowRequirementV1(FoundationModel):
    requirement_id: str
    statement: str = Field(min_length=1)
    premises: tuple[ShadowPremiseSpecV1, ...] = Field(min_length=1)
    readiness_rule: Literal["all_required_premises_positive"] = (
        "all_required_premises_positive"
    )

    @model_validator(mode="after")
    def validate_roster(self) -> "ShadowRequirementV1":
        ids = [premise.premise_id for premise in self.premises]
        if len(set(ids)) != len(ids):
            raise ValueError("requirement premise roster contains duplicates")
        return self


class ShadowActionV1(FoundationModel):
    action_id: str
    request: str = Field(min_length=1)
    cost: StrictInt = Field(ge=1)
    may_update: tuple[str, ...] = ()


class ShadowModelReceiptV1(FoundationModel):
    contract: Literal["casepath.shadow-model-receipt/1.0.0"] = (
        "casepath.shadow-model-receipt/1.0.0"
    )
    record_id: str
    model_id: str
    model_resolved_path: str
    resolved_config_sha256: str
    weight_index_sha256: str
    runner_sha256: str
    runtime: dict[str, Any]
    settings: dict[str, Any]
    input_sha256: str
    rendered_chat_sha256: str
    output_sha256: str
    input_tokens: StrictInt = Field(ge=0)
    output_tokens: StrictInt = Field(ge=0)
    finish_reason: str
    failure: str | None
    cost_usd: float = Field(ge=0)
    receipt_sha256: str


class SourcePreservingShadowRequestV1(FoundationModel):
    contract: Literal["casepath.source-preserving-shadow-request/1.0.0"] = (
        "casepath.source-preserving-shadow-request/1.0.0"
    )
    operation_id: str
    phase: Literal["initial", "post_action", "correction_only"]
    sources: tuple[ShadowSourceV1, ...] = Field(min_length=1)
    requirement: ShadowRequirementV1
    previous_premises: tuple[ShadowPremiseV1, ...] = ()
    actions: tuple[ShadowActionV1, ...] = ()
    applied_action_id: str | None = None
    corrections: tuple[ProposedShadowCorrectionV1, ...] = ()
    raw_model_output: str | None = None
    model_receipt: ShadowModelReceiptV1 | None = None


class ShadowQuarantineV1(FoundationModel):
    contract: Literal["casepath.shadow-quarantine/1.0.0"] = (
        "casepath.shadow-quarantine/1.0.0"
    )
    kind: Literal["support", "correction", "action", "prior_support"]
    premise_id: str | None
    record_id: str
    reason: str
    observed_sha256: str


def premise_state_sha256(premises: tuple[ShadowPremiseV1, ...] | list[ShadowPremiseV1]) -> str:
    return digest_value(
        [
            premise.model_dump(mode="json")
            for premise in sorted(premises, key=lambda value: value.premise_id)
        ]
    )


def _span_is_exact(
    span: ShadowSpanV1,
    source_by_id: dict[str, ShadowSourceV1],
    *,
    premise_id: str,
) -> tuple[bool, str]:
    source = source_by_id.get(span.source_id)
    if source is None:
        return False, "unknown_source"
    if span.source_version != source.source_version:
        return False, "source_version_mismatch"
    if span.source_sha256 != source.content_sha256:
        return False, "source_hash_mismatch"
    if premise_id not in source.allowed_premise_ids:
        return False, "source_scope_mismatch"
    if span.text_end > len(source.decoded_text):
        return False, "text_offset_out_of_bounds"
    if source.decoded_text[span.text_start : span.text_end] != span.exact_text:
        return False, "exact_text_mismatch"
    byte_start = len(source.decoded_text[: span.text_start].encode("utf-8"))
    byte_end = len(source.decoded_text[: span.text_end].encode("utf-8"))
    if span.byte_start != byte_start or span.byte_end != byte_end:
        return False, "byte_offset_mismatch"
    if span.span_sha256 != digest_text(span.exact_text):
        return False, "span_hash_mismatch"
    return True, "exact"


def _support_material(bundle: ShadowSupportBundleV1) -> dict[str, Any]:
    return bundle.model_dump(
        mode="json",
        exclude={"support_id", "model_receipt_sha256"},
    )


def _support_is_valid(
    bundle: ShadowSupportBundleV1,
    source_by_id: dict[str, ShadowSourceV1],
    premise: ShadowPremiseSpecV1,
) -> tuple[bool, str]:
    if bundle.premise_id != premise.premise_id:
        return False, "premise_id_mismatch"
    if bundle.scope != premise.scope:
        return False, "support_scope_mismatch"
    if not is_sha256(bundle.model_receipt_sha256):
        return False, "model_receipt_hash_invalid"
    if bundle.support_id != "support." + digest_value(_support_material(bundle)):
        return False, "support_identity_mismatch"
    for span in bundle.spans:
        passed, reason = _span_is_exact(
            span,
            source_by_id,
            premise_id=premise.premise_id,
        )
        if not passed:
            return False, reason
    return True, "exact"


def _new_span(source: ShadowSourceV1, start: int, exact_text: str) -> ShadowSpanV1:
    end = start + len(exact_text)
    return ShadowSpanV1(
        source_id=source.source_id,
        source_version=source.source_version,
        source_sha256=source.content_sha256,
        text_start=start,
        text_end=end,
        byte_start=len(source.decoded_text[:start].encode("utf-8")),
        byte_end=len(source.decoded_text[:end].encode("utf-8")),
        exact_text=exact_text,
        span_sha256=digest_text(exact_text),
    )


def exact_span(
    source: ShadowSourceV1,
    exact_text: str,
    *,
    occurrence: int = 0,
) -> ShadowSpanV1:
    starts: list[int] = []
    cursor = 0
    while True:
        found = source.decoded_text.find(exact_text, cursor)
        if found < 0:
            break
        starts.append(found)
        cursor = found + max(1, len(exact_text))
    if occurrence < 0 or occurrence >= len(starts):
        raise SourcePreservingShadowError("exact span is absent")
    return _new_span(source, starts[occurrence], exact_text)


def _locate_quotes(
    quotes: list[str],
    sources: tuple[ShadowSourceV1, ...],
    premise_id: str,
) -> tuple[tuple[ShadowSpanV1, ...] | None, str]:
    if not quotes or any(not isinstance(value, str) or not value for value in quotes):
        return None, "empty_support"
    spans: list[ShadowSpanV1] = []
    for quote in quotes:
        matches: list[tuple[ShadowSourceV1, int]] = []
        for source in sources:
            if premise_id not in source.allowed_premise_ids:
                continue
            cursor = 0
            while True:
                found = source.decoded_text.find(quote, cursor)
                if found < 0:
                    break
                matches.append((source, found))
                cursor = found + max(1, len(quote))
        if len(matches) != 1:
            return None, "non_exact_or_ambiguous_span"
        source, start = matches[0]
        spans.append(_new_span(source, start, quote))
    return tuple(spans), "exact"


def _new_support(
    *,
    premise: ShadowPremiseSpecV1,
    polarity: SupportPolarity,
    spans: tuple[ShadowSpanV1, ...],
    model_receipt_sha256: str,
) -> ShadowSupportBundleV1:
    partial = ShadowSupportBundleV1(
        support_id="support." + "0" * 64,
        premise_id=premise.premise_id,
        polarity=polarity,
        spans=spans,
        scope=premise.scope,
        supersedes=(),
        model_receipt_sha256=model_receipt_sha256,
    )
    return partial.model_copy(
        update={"support_id": "support." + digest_value(_support_material(partial))}
    )


def _model_receipt_is_valid(
    receipt: ShadowModelReceiptV1,
    raw_model_output: str,
) -> bool:
    payload = receipt.model_dump(mode="json", exclude={"receipt_sha256"})
    hashes = (
        receipt.resolved_config_sha256,
        receipt.weight_index_sha256,
        receipt.runner_sha256,
        receipt.input_sha256,
        receipt.rendered_chat_sha256,
        receipt.output_sha256,
    )
    return (
        all(is_sha256(value) for value in hashes)
        and receipt.output_sha256 == digest_text(raw_model_output)
        and receipt.receipt_sha256 == digest_value(payload)
        and receipt.finish_reason == "eos"
        and receipt.failure is None
    )


def _parse_model_output(raw: str) -> dict[str, Any]:
    suffix = "<|im_end|>"
    text = raw.strip()
    if text.endswith(suffix):
        text = text[: -len(suffix)].rstrip()
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise SourcePreservingShadowError("model output is not one JSON object") from exc
    if not isinstance(value, dict) or set(value) != {
        "atoms",
        "ready",
        "action",
        "question",
    }:
        raise SourcePreservingShadowError("model output envelope drifted")
    if (
        not isinstance(value["atoms"], list)
        or type(value["ready"]) is not bool
        or not isinstance(value["action"], str)
        or not isinstance(value["question"], str)
    ):
        raise SourcePreservingShadowError("model output envelope types are invalid")
    allowed_atom_fields = {
        "id",
        "status",
        "evidence",
        "evidence_spans",
        "positive_evidence_spans",
        "negative_evidence_spans",
        "rationale",
    }
    for atom in value["atoms"]:
        if (
            not isinstance(atom, dict)
            or not {"id", "status"}.issubset(atom)
            or not set(atom).issubset(allowed_atom_fields)
            or atom["status"] not in {"T", "F", "U", "C"}
        ):
            raise SourcePreservingShadowError("model atom schema drifted")
    return value


def _atom_quotes(atom: dict[str, Any], key: str = "evidence_spans") -> list[str]:
    if key in atom:
        value = atom[key]
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            raise SourcePreservingShadowError("model evidence span list is invalid")
        return value
    if key == "evidence_spans":
        value = atom.get("evidence", "")
        if not isinstance(value, str):
            raise SourcePreservingShadowError("model evidence is not text")
        return [value] if value else []
    return []


def _state_from_supports(supports: list[ShadowSupportBundleV1]) -> PremiseState:
    positive = any(bundle.polarity == "positive" for bundle in supports)
    negative = any(bundle.polarity == "negative" for bundle in supports)
    if positive and negative:
        return "C"
    if positive:
        return "T"
    if negative:
        return "F"
    return "U"


def _quarantine(
    *,
    kind: Literal["support", "correction", "action", "prior_support"],
    premise_id: str | None,
    record_id: str,
    reason: str,
    observed: Any,
) -> ShadowQuarantineV1:
    return ShadowQuarantineV1(
        kind=kind,
        premise_id=premise_id,
        record_id=record_id,
        reason=reason,
        observed_sha256=digest_value(observed),
    )


def _correction_relation(
    correction: ProposedShadowCorrectionV1,
    *,
    status: Literal["applied", "quarantined"],
    reason: str,
) -> ShadowCorrectionRelationV1:
    material = {
        **correction.model_dump(mode="json"),
        "contract": "casepath.shadow-correction-relation/1.0.0",
        "status": status,
        "reason": reason,
    }
    return ShadowCorrectionRelationV1(
        **material,
        correction_sha256=digest_value(material),
    )


def apply_source_preserving_shadow(
    request: SourcePreservingShadowRequestV1,
) -> dict[str, Any]:
    source_ids = [source.source_id for source in request.sources]
    if len(source_ids) != len(set(source_ids)):
        raise SourcePreservingShadowError("source roster contains duplicate identities")
    source_by_id = {source.source_id: source for source in request.sources}
    premise_specs = {
        premise.premise_id: premise for premise in request.requirement.premises
    }
    action_by_id = {action.action_id: action for action in request.actions}
    if len(action_by_id) != len(request.actions):
        raise SourcePreservingShadowError("action roster contains duplicates")
    if any(
        premise_id not in premise_specs
        for action in request.actions
        for premise_id in action.may_update
    ):
        raise SourcePreservingShadowError("action may-update scope is outside the requirement")

    if request.previous_premises:
        previous_by_id = {
            premise.premise_id: premise for premise in request.previous_premises
        }
        if set(previous_by_id) != set(premise_specs) or len(previous_by_id) != len(
            request.previous_premises
        ):
            raise SourcePreservingShadowError("previous premise roster drifted")
    else:
        previous_by_id = {
            premise_id: ShadowPremiseV1(premise_id=premise_id, state="U")
            for premise_id in premise_specs
        }

    previous_state_sha = premise_state_sha256(list(previous_by_id.values()))
    quarantines: list[ShadowQuarantineV1] = []
    active: dict[str, dict[str, ShadowSupportBundleV1]] = {
        premise_id: {} for premise_id in premise_specs
    }
    historical: dict[str, ShadowSupportBundleV1] = {}
    relations: dict[str, list[ShadowCorrectionRelationV1]] = {
        premise_id: list(previous_by_id[premise_id].correction_relations)
        for premise_id in premise_specs
    }
    tombstones = {
        support_id
        for premise in request.previous_premises
        for relation in premise.correction_relations
        if relation.status == "applied"
        for support_id in relation.target_support_ids
    }
    for premise_id, previous in previous_by_id.items():
        spec = premise_specs[premise_id]
        for bundle in previous.support_bundles:
            passed, reason = _support_is_valid(bundle, source_by_id, spec)
            if not passed:
                quarantines.append(
                    _quarantine(
                        kind="prior_support",
                        premise_id=premise_id,
                        record_id=bundle.support_id,
                        reason=reason,
                        observed=bundle.model_dump(mode="json"),
                    )
                )
                continue
            historical[bundle.support_id] = bundle
            if bundle.support_id not in tombstones:
                active[premise_id][bundle.support_id] = bundle
        actual = _state_from_supports(list(active[premise_id].values()))
        if actual != previous.state:
            quarantines.append(
                _quarantine(
                    kind="prior_support",
                    premise_id=premise_id,
                    record_id=f"state.{premise_id}",
                    reason="prior_state_does_not_match_valid_active_support",
                    observed={"declared": previous.state, "derived": actual},
                )
            )

    for correction in request.corrections:
        reason = "applied"
        spec = premise_specs.get(correction.premise_id)
        targets = [historical.get(support_id) for support_id in correction.target_support_ids]
        if spec is None:
            reason = "unknown_premise"
        elif correction.expected_parent_state_sha256 != previous_state_sha:
            reason = "stale_parent_state"
        elif correction.scope is None:
            reason = "unknown_correction_scope"
        elif correction.scope != spec.scope:
            reason = "correction_scope_mismatch"
        elif any(target is None for target in targets):
            reason = "unknown_target_support"
        elif any(target.premise_id != correction.premise_id for target in targets if target):
            reason = "cross_premise_target"
        elif set(correction.target_source_versions) != set(correction.target_support_ids):
            reason = "target_version_roster_mismatch"
        elif any(
            tuple(sorted({span.source_version for span in target.spans}))
            != tuple(sorted(correction.target_source_versions[target.support_id]))
            for target in targets
            if target
        ):
            reason = "target_source_version_mismatch"
        else:
            for span in correction.evidence_spans:
                passed, span_reason = _span_is_exact(
                    span,
                    source_by_id,
                    premise_id=correction.premise_id,
                )
                if not passed:
                    reason = f"correction_{span_reason}"
                    break
        if reason == "applied":
            for support_id in correction.target_support_ids:
                active[correction.premise_id].pop(support_id, None)
                tombstones.add(support_id)
            relation = _correction_relation(
                correction,
                status="applied",
                reason=reason,
            )
        else:
            relation = _correction_relation(
                correction,
                status="quarantined",
                reason=reason,
            )
            quarantines.append(
                _quarantine(
                    kind="correction",
                    premise_id=correction.premise_id,
                    record_id=correction.correction_id,
                    reason=reason,
                    observed=correction.model_dump(mode="json"),
                )
            )
        if correction.premise_id in relations:
            relations[correction.premise_id].append(relation)

    model_value: dict[str, Any] | None = None
    receipt_sha = "0" * 64
    if request.phase != "correction_only":
        if request.raw_model_output is None or request.model_receipt is None:
            raise SourcePreservingShadowError("shadow interpretation lacks its model receipt")
        if not _model_receipt_is_valid(request.model_receipt, request.raw_model_output):
            raise SourcePreservingShadowError("shadow model receipt identity is invalid")
        receipt_sha = request.model_receipt.receipt_sha256
        model_value = _parse_model_output(request.raw_model_output)
        atom_ids = [atom.get("id") for atom in model_value["atoms"]]
        if len(atom_ids) != len(set(atom_ids)) or set(atom_ids) != set(premise_specs):
            raise SourcePreservingShadowError("model premise roster drifted")

        if request.phase == "initial":
            allowed_updates = set(premise_specs)
        else:
            if request.applied_action_id in {None, "none"}:
                allowed_updates = set()
            else:
                action = action_by_id.get(request.applied_action_id)
                if action is None:
                    raise SourcePreservingShadowError("applied action is absent")
                if not any(
                    source.acquisition_action_id == action.action_id
                    for source in request.sources
                ):
                    raise SourcePreservingShadowError(
                        "post-action interpretation lacks an action-bound source"
                    )
                allowed_updates = set(action.may_update)

        for atom in model_value["atoms"]:
            premise_id = atom["id"]
            spec = premise_specs[premise_id]
            declared = atom["status"]
            current_state = _state_from_supports(list(active[premise_id].values()))
            if premise_id not in allowed_updates:
                if declared != current_state:
                    quarantines.append(
                        _quarantine(
                            kind="support",
                            premise_id=premise_id,
                            record_id=request.model_receipt.record_id,
                            reason="outside_action_may_update_scope",
                            observed=atom,
                        )
                    )
                continue
            if declared == "U":
                # Unknown is absence of a new admissible assertion.  It never
                # withdraws old support; withdrawals require an exact correction.
                continue
            proposals: list[tuple[SupportPolarity, list[str]]] = []
            if declared == "T":
                proposals.append(("positive", _atom_quotes(atom)))
            elif declared == "F":
                proposals.append(("negative", _atom_quotes(atom)))
            else:
                proposals.extend(
                    [
                        ("positive", _atom_quotes(atom, "positive_evidence_spans")),
                        ("negative", _atom_quotes(atom, "negative_evidence_spans")),
                    ]
                )
            for polarity, quotes in proposals:
                spans, reason = _locate_quotes(quotes, request.sources, premise_id)
                if spans is None:
                    quarantines.append(
                        _quarantine(
                            kind="support",
                            premise_id=premise_id,
                            record_id=request.model_receipt.record_id,
                            reason=reason,
                            observed={"polarity": polarity, "quotes": quotes},
                        )
                    )
                    continue
                bundle = _new_support(
                    premise=spec,
                    polarity=polarity,
                    spans=spans,
                    model_receipt_sha256=receipt_sha,
                )
                if bundle.support_id in tombstones:
                    quarantines.append(
                        _quarantine(
                            kind="support",
                            premise_id=premise_id,
                            record_id=bundle.support_id,
                            reason="support_was_explicitly_superseded",
                            observed=bundle.model_dump(mode="json"),
                        )
                    )
                    continue
                if bundle.support_id not in active[premise_id]:
                    active[premise_id][bundle.support_id] = bundle
                    historical[bundle.support_id] = bundle

    premises: list[ShadowPremiseV1] = []
    atom_by_id = {
        atom["id"]: atom for atom in model_value["atoms"]
    } if model_value is not None else {}
    for premise_id in sorted(premise_specs):
        previous = previous_by_id[premise_id]
        atom = atom_by_id.get(premise_id, {})
        rationale = atom.get("rationale", previous.rationale)
        if not isinstance(rationale, str):
            raise SourcePreservingShadowError("model rationale is not text")
        bundles = tuple(
            sorted(active[premise_id].values(), key=lambda value: value.support_id)
        )
        premises.append(
            ShadowPremiseV1(
                premise_id=premise_id,
                state=_state_from_supports(list(bundles)),
                support_bundles=bundles,
                correction_relations=tuple(relations[premise_id]),
                rationale=rationale,
            )
        )

    next_action: dict[str, Any] | None = None
    reported_ready: bool | None = None
    if model_value is not None:
        reported_ready = model_value["ready"]
        selected = model_value["action"]
        if selected != "none":
            action = action_by_id.get(selected)
            if action is None:
                quarantines.append(
                    _quarantine(
                        kind="action",
                        premise_id=None,
                        record_id=selected,
                        reason="unknown_action",
                        observed={"action": selected},
                    )
                )
            else:
                # Selection is validated against realizable effects, not only
                # current U/C values.  F premises remain updateable.
                next_action = {
                    "action_id": action.action_id,
                    "request": action.request,
                    "cost": action.cost,
                    "may_update": list(action.may_update),
                }

    shadow_ready = all(premise.state == "T" for premise in premises)
    available_sources = [
        {
            "source_id": source.source_id,
            "source_version": source.source_version,
            "content_sha256": source.content_sha256,
            "size_bytes": len(base64.b64decode(source.content_b64)),
            "acquired_at": source.acquired_at,
            "acquisition_action_id": source.acquisition_action_id,
        }
        for source in sorted(request.sources, key=lambda value: value.source_id)
    ]
    material: dict[str, Any] = {
        "contract": "casepath.source-preserving-shadow-response/1.0.0",
        "adapter_id": SHADOW_ADAPTER_ID,
        "operation_id": request.operation_id,
        "mode": "shadow_non_authoritative",
        "canonical_authority": "existing_intake_grammar_and_claim_loop_reducer",
        "canonical_state_mutated": False,
        "semantic_admission": "fallible_exact_span_serialization_not_truth",
        "available_sources": available_sources,
        "premises": [premise.model_dump(mode="json") for premise in premises],
        "previous_state_sha256": previous_state_sha,
        "shadow_state_sha256": premise_state_sha256(premises),
        "reported_ready": reported_ready,
        "shadow_ready": shadow_ready,
        "readiness_disagreement": (
            reported_ready is not None and reported_ready != shadow_ready
        ),
        "next_action": next_action,
        "quarantines": [value.model_dump(mode="json") for value in quarantines],
        "model_receipt": (
            request.model_receipt.model_dump(mode="json")
            if request.model_receipt is not None
            else None
        ),
    }
    return {**material, "response_sha256": digest_value(material)}


def create_source_preserving_shadow_router() -> APIRouter:
    router = APIRouter(tags=["source-preserving-shadow"])

    @router.post(SHADOW_ROUTE)
    def admit_source_preserving_shadow(
        body: SourcePreservingShadowRequestV1,
    ) -> dict[str, Any]:
        try:
            return apply_source_preserving_shadow(body)
        except (SourcePreservingShadowError, TypeError, ValueError) as exc:
            raise HTTPException(422, str(exc)) from exc

    return router


__all__ = [
    "SHADOW_ADAPTER_ID",
    "SHADOW_ROUTE",
    "ProposedShadowCorrectionV1",
    "ShadowActionV1",
    "ShadowModelReceiptV1",
    "ShadowPremiseSpecV1",
    "ShadowPremiseV1",
    "ShadowRequirementV1",
    "ShadowScopeV1",
    "ShadowSourceV1",
    "ShadowSpanV1",
    "SourcePreservingShadowError",
    "SourcePreservingShadowRequestV1",
    "apply_source_preserving_shadow",
    "create_source_preserving_shadow_router",
    "exact_span",
    "premise_state_sha256",
]
