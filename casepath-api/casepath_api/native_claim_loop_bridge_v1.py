"""Opt-in bridge from a qualified native proposal to the durable ClaimLoop.

The bridge treats model output as a provisional, source-relative proposal.  It
creates a declarative inquiry playbook, and later admits an answer only after
every cited text span and native page has been resolved against server-observed
source bytes.  Native pages remain opaque provenance rather than OCR or an
entailment oracle.  Neither a valid pointer nor a completed loop certifies legal
truth/readiness.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
from threading import RLock
from typing import Any, Callable, Mapping

from .claim_loop import (
    ClaimLoopError,
    CorrectionToolResult,
    ToolResult,
    ToolResultStatus,
    adapter_implementation_sha256_v1,
)
from .claim_loop_contracts import (
    AcquisitionReceiptV1,
    CanonicalFactInterpretationV1,
    ClaimObservation,
    ClaimSourceRef,
    CorrectionEffect,
    EvidenceAction,
    NativeProposalRevisionV1,
    ToolArtifactReceipt,
)
from .claim_loop_service import ClaimLoopService, ClaimLoopServiceError
from .foundation.common import canonical_json_bytes, digest_text, digest_value, is_sha256
from .playbook_template import PlaybookTemplate
from .workspace_claim_loop_v1 import (
    DeterministicTemplateCyclePipelineRouter,
    WORKSPACE_CLAIM_LOOP_SESSION_ID,
)


NATIVE_SOURCE_SET_ADAPTER_ID = "casepath.native-source-set-adapter/1.0.0"
NATIVE_SOURCE_CORRECTION_ADAPTER_ID = (
    "casepath.native-source-correction-adapter/1.0.0"
)
LEGACY_PACKET_CONTRACT = "casepath.native-source-set-observation/1.0.0"
ROLE_PACKET_CONTRACT = "casepath.native-source-set-observation/1.1.0"
MULTIMODAL_PACKET_CONTRACT = "casepath.native-source-set-observation/1.2.0"
PACKET_CONTRACT = "casepath.native-source-set-observation/1.3.0"


class NativeClaimLoopBridgeError(ValueError):
    pass


_NATIVE_NEED_STATES = {
    "missing",
    "partial",
    "pending",
    "received",
    "contested",
    "conditional",
    "withdrawn",
    "uncertain",
}


def _validated_native_until(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value or len(value) > 80:
        raise NativeClaimLoopBridgeError("native need until must be aware")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise NativeClaimLoopBridgeError("native need until must be aware") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise NativeClaimLoopBridgeError("native need until must be aware")
    return value


def validated_native_proposed_action_v1(value: Any) -> dict[str, Any] | None:
    """Validate a display-only action proposed by the fallible native actor.

    This value has no dispatch, fact, sufficiency, or readiness effect.  Keeping
    it closed and bounded lets the workspace render the actor's follow-up
    without deriving action text from an admitted answer.
    """

    if value is None:
        return None
    if not isinstance(value, Mapping) or set(value) != {
        "audience",
        "enabled",
        "requested_contents",
    }:
        raise ClaimLoopError("native proposed action fields are invalid")
    audience = value.get("audience")
    enabled = value.get("enabled")
    contents = value.get("requested_contents")
    if audience not in {"internal", "provider", "claimant", "authority"} or not isinstance(enabled, bool):
        raise ClaimLoopError("native proposed action routing is invalid")
    if (
        not isinstance(contents, list)
        or len(contents) > 8
        or (enabled and not contents)
        or any(
            not isinstance(item, str)
            or not item.strip()
            or len(item) > 240
            or item != item.strip()
            for item in contents
        )
        or len(contents) != len(set(contents))
    ):
        raise ClaimLoopError("native proposed action contents are invalid")
    return {
        "audience": audience,
        "enabled": enabled,
        "requested_contents": list(contents),
    }


def _module_sha256() -> str:
    return sha256(Path(__file__).read_bytes()).hexdigest()


def _closed_packet(content: str) -> dict[str, Any]:
    try:
        value = json.loads(content)
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise ClaimLoopError("native source-set packet is not JSON") from exc
    legacy_fields = {
        "contract",
        "claim_id",
        "need_id",
        "description",
        "answer",
        "state",
        "observed_at",
        "source_prefix_sha256",
        "proposal_item_sha256",
        "source_refs",
        "source_artifacts",
    }
    role_preserving_fields = {
        *legacy_fields,
        "mutation_kind",
        "context_source_refs",
        "context_image_receipts",
        "evidence",
        "correction_transition_binding",
    }
    multimodal_fields = {
        *(role_preserving_fields - {"context_image_receipts"}),
        "native_image_receipts",
    }
    proposed_action_fields = {*multimodal_fields, "proposed_action"}
    if not isinstance(value, dict):
        raise ClaimLoopError("native source-set packet fields are not closed")
    contract = value.get("contract")
    expected_fields = (
        legacy_fields
        if contract == LEGACY_PACKET_CONTRACT
        else role_preserving_fields
        if contract == ROLE_PACKET_CONTRACT
        else multimodal_fields
        if contract == MULTIMODAL_PACKET_CONTRACT
        else proposed_action_fields
        if contract == PACKET_CONTRACT
        else None
    )
    if expected_fields is None:
        raise ClaimLoopError("native source-set packet contract is invalid")
    if set(value) != expected_fields:
        raise ClaimLoopError("native source-set packet fields are not closed")
    if canonical_json_bytes(value).decode("utf-8") != content:
        raise ClaimLoopError("native source-set packet is not canonical JSON")
    if not isinstance(value.get("answer"), str) or not value["answer"].strip():
        raise ClaimLoopError("native source-set packet has no answer")
    if not isinstance(value.get("source_refs"), list) or not value["source_refs"]:
        raise ClaimLoopError("native source-set packet has no evidence")
    if len(value["source_refs"]) > 20:
        raise ClaimLoopError("native source-set packet exceeds the source-ref bound")
    if not isinstance(value.get("source_artifacts"), list):
        raise ClaimLoopError("native source-set packet has no source artifacts")
    if contract in {
        ROLE_PACKET_CONTRACT,
        MULTIMODAL_PACKET_CONTRACT,
        PACKET_CONTRACT,
    }:
        if value.get("mutation_kind") not in {"observation", "correction"}:
            raise ClaimLoopError("native source-set mutation kind is invalid")
        if not isinstance(value.get("context_source_refs"), list):
            raise ClaimLoopError("native source-set context references are invalid")
        image_field = (
            "context_image_receipts"
            if contract == ROLE_PACKET_CONTRACT
            else "native_image_receipts"
        )
        if not isinstance(value.get(image_field), list):
            raise ClaimLoopError("native source-set image receipts are invalid")
        if not isinstance(value.get("evidence"), list) or not value["evidence"]:
            raise ClaimLoopError("native source-set role evidence is invalid")
        if (
            len(value["source_refs"])
            + len(value["context_source_refs"])
            + len(value[image_field])
            > 20
        ):
            raise ClaimLoopError("native source-set packet exceeds the evidence bound")
    if contract == PACKET_CONTRACT:
        validated_native_proposed_action_v1(value.get("proposed_action"))
    return value


def _source_artifact_map(packet: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in packet["source_artifacts"]:
        if (
            not isinstance(row, dict)
            or set(row)
            != {
                "artifact_id",
                "filename",
                "media_type",
                "received_at",
                "page_count",
                "sha256",
                "extracted_pages",
                "parent_artifact_id",
                "parent_artifact_sha256",
            }
            or row.get("artifact_id") in result
            or not is_sha256(row.get("sha256"))
            or not is_sha256(row.get("parent_artifact_sha256"))
        ):
            raise ClaimLoopError("native source artifact registry is invalid")
        pages = row.get("extracted_pages")
        if not isinstance(pages, list) or not pages:
            raise ClaimLoopError("native source artifact has no text page")
        if (
            len(pages) != 1
            or pages[0].get("page") != 1
            or not isinstance(pages[0].get("text"), str)
            or digest_text(pages[0]["text"]) != row["sha256"]
        ):
            raise ClaimLoopError("native source artifact text hash is invalid")
        result[str(row["artifact_id"])] = deepcopy(row)
    return result


def _validated_ref_field(
    packet: Mapping[str, Any], field: str
) -> tuple[ClaimSourceRef, ...]:
    artifacts = _source_artifact_map(packet)
    refs: list[ClaimSourceRef] = []
    identities: set[str] = set()
    for raw in packet[field]:
        try:
            ref = ClaimSourceRef.model_validate(raw)
        except (TypeError, ValueError) as exc:
            raise ClaimLoopError("native source reference is invalid") from exc
        if ref.adapter_id != NATIVE_SOURCE_SET_ADAPTER_ID:
            raise ClaimLoopError("native source reference adapter is invalid")
        identity = digest_value(ref.model_dump(mode="json"))
        if identity in identities:
            raise ClaimLoopError("native source reference is duplicated")
        identities.add(identity)
        artifact = artifacts.get(ref.source_id)
        pages = artifact.get("extracted_pages") if artifact else None
        page = next(
            (
                row
                for row in pages or []
                if isinstance(row, Mapping) and row.get("page") == ref.page
            ),
            None,
        )
        text = page.get("text") if isinstance(page, Mapping) else None
        if (
            artifact is None
            or artifact["sha256"] != ref.source_sha256
            or ref.locator_kind != "text_quote"
            or not isinstance(text, str)
            or ref.text_start is None
            or ref.text_end is None
            or ref.text_end > len(text)
            or text[ref.text_start : ref.text_end] != ref.sanitized_excerpt
            or ref.span_sha256 != digest_text(ref.sanitized_excerpt or "")
        ):
            raise ClaimLoopError("native source reference differs from admitted bytes")
        refs.append(ref)
    return tuple(refs)


def _validated_refs(packet: Mapping[str, Any]) -> tuple[ClaimSourceRef, ...]:
    return _validated_ref_field(packet, "source_refs")


def _pointer_claim_ref(
    pointer: Mapping[str, Any], source_prefix_sha256: str
) -> ClaimSourceRef:
    try:
        return ClaimSourceRef(
            source_id=str(pointer["view_id"]),
            source_sha256=str(pointer["view_text_sha256"]),
            source_version="native-prefix." + source_prefix_sha256,
            locator_kind="text_quote",
            page=1,
            sanitized_excerpt=str(pointer["text"]),
            text_start=int(pointer["char_start"]),
            text_end=int(pointer["char_end"]),
            span_sha256=str(pointer["text_sha256"]),
            adapter_id=NATIVE_SOURCE_SET_ADAPTER_ID,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ClaimLoopError("native text evidence pointer is invalid") from exc


def _stable_span_identity(ref: ClaimSourceRef) -> str:
    return digest_value(
        {
            "source_id": ref.source_id,
            "source_sha256": ref.source_sha256,
            "locator_kind": ref.locator_kind,
            "page": ref.page,
            "text_start": ref.text_start,
            "text_end": ref.text_end,
            "span_sha256": ref.span_sha256,
        }
    )


def _validate_image_receipt(
    pointer: Mapping[str, Any], receipt: Mapping[str, Any]
) -> None:
    expected_receipt_fields = {
        "image_id",
        "image_path",
        "media_type",
        "page_index",
        "raw_artifact_sha256",
        "sha256",
        "size_bytes",
        "source_id",
        "view_id",
    }
    if (
        set(receipt) != expected_receipt_fields
        or receipt.get("image_id") != pointer.get("ref")
        or receipt.get("source_id") != pointer.get("source_id")
        or receipt.get("view_id") != pointer.get("view_id")
        or receipt.get("page_index") != pointer.get("page_index")
        or receipt.get("sha256") != pointer.get("image_sha256")
        or receipt.get("raw_artifact_sha256")
        != pointer.get("raw_artifact_sha256")
        or receipt.get("media_type") not in {"image/png", "image/jpeg"}
        or type(receipt.get("size_bytes")) is not int
        or receipt["size_bytes"] <= 0
        or not is_sha256(receipt.get("sha256"))
        or not is_sha256(receipt.get("raw_artifact_sha256"))
        or not isinstance(receipt.get("image_path"), str)
    ):
        raise ClaimLoopError("native image receipt is invalid")
    path = Path(receipt["image_path"])
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ClaimLoopError("native image bytes are unavailable") from exc
    if (
        path.is_symlink()
        or len(raw) != receipt["size_bytes"]
        or sha256(raw).hexdigest() != receipt["sha256"]
    ):
        raise ClaimLoopError("native image differs from admitted bytes")


def _packet_image_receipts(packet: Mapping[str, Any]) -> list[dict[str, Any]]:
    field = (
        "context_image_receipts"
        if packet.get("contract") == ROLE_PACKET_CONTRACT
        else "native_image_receipts"
    )
    return list(packet.get(field, []))


def _packet_image_role_count(
    packet: Mapping[str, Any], roles: set[str]
) -> int:
    receipt_ids = {
        row.get("image_id") for row in _packet_image_receipts(packet)
    }
    return sum(
        1
        for pointer in packet.get("evidence", [])
        if isinstance(pointer, Mapping)
        and pointer.get("kind") == "native_image"
        and pointer.get("ref") in receipt_ids
        and pointer.get("role") in roles
    )


def _validated_role_evidence(packet: Mapping[str, Any]) -> None:
    """Validate every actor pointer while keeping context out of fact semantics."""

    if packet.get("contract") == LEGACY_PACKET_CONTRACT:
        _validated_refs(packet)
        return
    semantic_refs = _validated_refs(packet)
    context_refs = _validated_ref_field(packet, "context_source_refs")
    semantic_by_hash = {
        digest_value(ref.model_dump(mode="json")): ref for ref in semantic_refs
    }
    context_by_hash = {
        digest_value(ref.model_dump(mode="json")): ref for ref in context_refs
    }
    if set(semantic_by_hash) & set(context_by_hash):
        raise ClaimLoopError("native source reference has conflicting roles")
    image_receipts = _packet_image_receipts(packet)
    image_by_id = {
        row.get("image_id"): row
        for row in image_receipts
        if isinstance(row, Mapping) and isinstance(row.get("image_id"), str)
    }
    if len(image_by_id) != len(image_receipts):
        raise ClaimLoopError("native image receipt is duplicated")

    mutation = packet["mutation_kind"]
    semantic_roles = (
        {"support", "contrary"} if mutation == "observation" else {"correction"}
    )
    allowed_roles = {"support", "contrary", "context"}
    if mutation == "correction":
        allowed_roles.add("correction")
    seen_pointer_ids: set[str] = set()
    seen_text_hashes: set[str] = set()
    seen_image_ids: set[str] = set()
    for pointer in packet["evidence"]:
        if not isinstance(pointer, Mapping):
            raise ClaimLoopError("native role evidence pointer is invalid")
        role = pointer.get("role")
        pointer_id = pointer.get("pointer_id")
        if (
            role not in allowed_roles
            or not isinstance(pointer_id, str)
            or not pointer_id
            or pointer_id in seen_pointer_ids
        ):
            raise ClaimLoopError("native role evidence pointer is invalid")
        seen_pointer_ids.add(pointer_id)
        kind = pointer.get("kind")
        if kind == "text":
            ref = _pointer_claim_ref(pointer, str(packet["source_prefix_sha256"]))
            identity = digest_value(ref.model_dump(mode="json"))
            expected = semantic_by_hash if role in semantic_roles else context_by_hash
            if identity not in expected or identity in seen_text_hashes:
                raise ClaimLoopError("native text evidence role binding is invalid")
            seen_text_hashes.add(identity)
        elif kind == "native_image":
            if packet.get("contract") == ROLE_PACKET_CONTRACT and role != "context":
                raise ClaimLoopError(
                    "native image evidence is provenance-only context"
                )
            if role not in {"context", "support", "contrary"}:
                raise ClaimLoopError("native image evidence role is invalid")
            if mutation == "correction" and role != "context":
                raise ClaimLoopError(
                    "native correction requires exact text correction evidence"
                )
            receipt = image_by_id.get(pointer.get("ref"))
            if receipt is None or pointer.get("ref") in seen_image_ids:
                raise ClaimLoopError("native image evidence binding is invalid")
            _validate_image_receipt(pointer, receipt)
            if not any(
                artifact.get("parent_artifact_id") == pointer.get("source_id")
                and artifact.get("parent_artifact_sha256")
                == pointer.get("raw_artifact_sha256")
                for artifact in packet["source_artifacts"]
            ):
                raise ClaimLoopError(
                    "native image parent is absent from admitted source artifacts"
                )
            seen_image_ids.add(str(pointer["ref"]))
        else:
            raise ClaimLoopError("native role evidence kind is invalid")
    if seen_text_hashes != {*semantic_by_hash, *context_by_hash}:
        raise ClaimLoopError("native source reference role set is incomplete")
    if seen_image_ids != set(image_by_id):
        raise ClaimLoopError("native image role set is incomplete")
    if mutation == "correction" and not any(
        row.get("role") == "correction" for row in packet["evidence"]
    ):
        raise ClaimLoopError("native correction has no correction-role evidence")
    binding = packet["correction_transition_binding"]
    if mutation == "observation" and binding is not None:
        raise ClaimLoopError("native observation has a correction binding")
    if binding is not None:
        fields = {
            "contract",
            "need_id",
            "prior_observation_sha256",
            "prior_value_sha256",
            "correction_pointer_ids",
            "scope",
            "source_change_kind",
            "prior_source_fact_replacement_established",
            "retained_prior_source_ref_sha256s",
            "durable_inquiry_description_sha256",
            "proposal_description_sha256",
            "description_relation",
            "binding_sha256",
        }
        payload = {key: value for key, value in binding.items() if key != "binding_sha256"} if isinstance(binding, Mapping) else {}
        expected_pointer_ids = [
            row["pointer_id"]
            for row in packet["evidence"]
            if row.get("role") == "correction"
        ]
        if (
            not isinstance(binding, Mapping)
            or set(binding) != fields
            or binding.get("contract")
            != "casepath.native-correction-transition-binding/1.0.0"
            or binding.get("need_id") != packet.get("need_id")
            or binding.get("scope") != "extend_prior_source_relative_answer"
            or binding.get("source_change_kind") != "answer_extension"
            or binding.get("prior_source_fact_replacement_established") is not False
            or binding.get("description_relation")
            != "same_durable_need_id_with_refined_proposal_description"
            or not is_sha256(binding.get("prior_observation_sha256"))
            or not is_sha256(binding.get("prior_value_sha256"))
            or not is_sha256(binding.get("durable_inquiry_description_sha256"))
            or not is_sha256(binding.get("proposal_description_sha256"))
            or binding.get("correction_pointer_ids") != expected_pointer_ids
            or not isinstance(
                binding.get("retained_prior_source_ref_sha256s"), list
            )
            or any(
                not is_sha256(value)
                for value in binding.get("retained_prior_source_ref_sha256s", [])
            )
            or binding.get("binding_sha256") != digest_value(payload)
        ):
            raise ClaimLoopError("native correction transition binding is invalid")


class NativeSourceSetAdapterV1:
    adapter_id = NATIVE_SOURCE_SET_ADAPTER_ID
    implementation_id = "casepath.native-source-set-adapter/1.0.0"

    def __init__(self) -> None:
        self._lock = RLock()
        self._staged: dict[str, str] = {}

    @property
    def implementation_source_sha256(self) -> str:
        return _module_sha256()

    @property
    def implementation_sha256(self) -> str:
        return adapter_implementation_sha256_v1(
            adapter_id=self.adapter_id,
            implementation_id=self.implementation_id,
            implementation_source_sha256=self.implementation_source_sha256,
        )

    def stage(self, action_id: str, packet: Mapping[str, Any]) -> None:
        content = canonical_json_bytes(packet).decode("utf-8")
        _validated_role_evidence(_closed_packet(content))
        with self._lock:
            existing = self._staged.get(action_id)
            if existing is not None and existing != content:
                raise NativeClaimLoopBridgeError("native action already has other bytes")
            self._staged[action_id] = content

    def unstage(self, action_id: str) -> None:
        with self._lock:
            self._staged.pop(action_id, None)

    def execute(
        self,
        *,
        action: EvidenceAction,
        state: Any,
        idempotency_key: str,
        timestamp: str,
    ) -> ToolResult:
        with self._lock:
            content = self._staged.get(action.action_id)
        if content is None:
            raise ClaimLoopError("native source-set action has no staged receipt")
        packet = _closed_packet(content)
        if packet["claim_id"] != state.claim_id:
            raise ClaimLoopError("native source-set packet is cross-claim")
        return ToolResult(
            status=ToolResultStatus.OBSERVED,
            sanitized_content=content,
            artifact_source_version=state.record_version,
            artifact_page_count=1,
            source_locator="native-source-set:" + digest_value(packet),
        )


class NativeSourceCorrectionAdapterV1:
    """Admit one later source record as a singleton, source-scoped correction."""

    adapter_id = NATIVE_SOURCE_CORRECTION_ADAPTER_ID

    def __init__(self) -> None:
        self._lock = RLock()
        self._staged: dict[str, dict[str, Any]] = {}

    def stage(
        self, source_artifact_receipt_sha256: str, packet: Mapping[str, Any]
    ) -> None:
        closed = _closed_packet(canonical_json_bytes(packet).decode("utf-8"))
        _validated_role_evidence(closed)
        refs = _validated_refs(closed)
        if not refs or len({ref.source_id for ref in refs}) != 1:
            raise NativeClaimLoopBridgeError(
                "native correction requires exact spans from one source view"
            )
        with self._lock:
            existing = self._staged.get(source_artifact_receipt_sha256)
            if existing is not None and existing != closed:
                raise NativeClaimLoopBridgeError(
                    "native correction target already has other bytes"
                )
            self._staged[source_artifact_receipt_sha256] = deepcopy(closed)

    def unstage(self, source_artifact_receipt_sha256: str) -> None:
        with self._lock:
            self._staged.pop(source_artifact_receipt_sha256, None)

    def _packet(self, source_artifact: ToolArtifactReceipt) -> dict[str, Any]:
        with self._lock:
            value = self._staged.get(source_artifact.receipt_sha256)
        if value is None:
            raise ClaimLoopError("native correction has no staged source record")
        return deepcopy(value)

    def source_ref_for_correction(
        self, *, source_artifact: ToolArtifactReceipt, state: Any, timestamp: str
    ) -> ClaimSourceRef:
        del timestamp
        packet = self._packet(source_artifact)
        _validated_role_evidence(packet)
        refs = _validated_refs(packet)
        if packet["claim_id"] != state.claim_id or not refs:
            raise ClaimLoopError("native correction source is outside the target claim")
        return refs[0]

    def execute(
        self, *, source_artifact: ToolArtifactReceipt, state: Any, timestamp: str
    ) -> CorrectionToolResult:
        packet = self._packet(source_artifact)
        _validated_role_evidence(packet)
        refs = _validated_refs(packet)
        observation = source_artifact.observation
        binding = NativeSourceSetInterpreterV1._need_binding(
            state, str(packet["need_id"])
        )
        if (
            not refs
            or packet["claim_id"] != state.claim_id
            or binding["fact_id"] != observation.fact_id
            or binding["evidence_item_id"] != observation.evidence_item_id
        ):
            raise ClaimLoopError("native correction is not bound to its prior assertion")
        transition = packet["correction_transition_binding"]
        if (
            transition["durable_inquiry_description_sha256"]
            != digest_text(str(binding["description"]))
            or transition["proposal_description_sha256"]
            != digest_text(str(packet["description"]))
        ):
            raise ClaimLoopError(
                "native correction description provenance changed"
            )
        known = packet["state"] == "received"
        conflicting = packet["state"] == "contested"
        return CorrectionToolResult(
            effect=CorrectionEffect(
                fact_id=observation.fact_id,
                evidence_item_id=observation.evidence_item_id,
                value=str(packet["answer"]),
                fact_state="known" if known else "conflicting" if conflicting else "unknown",
                normalized_value="observed" if known else None,
                explanation=(
                    "A later fallible source-relative record extends only this "
                    "answer. It does not establish replacement of an old source "
                    "fact; all sibling observations and original bytes persist."
                ),
                evidence_status=(
                    "provided_sufficient" if known else "provided_insufficient"
                ),
            ),
            issuer_id=self.adapter_id,
            provenance_note=canonical_json_bytes(
                {
                    "contract": "casepath.native-correction-role-provenance/1.0.0",
                    "admitted_at": timestamp,
                    "correction_transition_binding_sha256": packet[
                        "correction_transition_binding"
                    ]["binding_sha256"],
                    "evidence_sha256": digest_value(packet["evidence"]),
                    "context_source_refs_sha256": digest_value(
                        packet["context_source_refs"]
                    ),
                    "native_image_receipts_sha256": digest_value(
                        _packet_image_receipts(packet)
                    ),
                    "durable_inquiry_description_sha256": transition[
                        "durable_inquiry_description_sha256"
                    ],
                    "proposal_description_sha256": transition[
                        "proposal_description_sha256"
                    ],
                }
            ).decode("utf-8"),
        )

    def validate_correction_source_binding(
        self, *, source_artifact: ToolArtifactReceipt, state: Any, correction: Any
    ) -> None:
        packet = self._packet(source_artifact)
        _validated_role_evidence(packet)
        refs = _validated_refs(packet)
        if (
            not refs
            or correction.source_ref != refs[0]
            or packet["claim_id"] != state.claim_id
            or correction.effect != self.execute(
                source_artifact=source_artifact,
                state=state,
                timestamp=correction.effective_at,
            ).effect
        ):
            raise ClaimLoopError("native correction source binding changed")

    def correction_source_binding(
        self, *, source_artifact: ToolArtifactReceipt, state: Any, correction: Any
    ) -> dict[str, Any]:
        self.validate_correction_source_binding(
            source_artifact=source_artifact,
            state=state,
            correction=correction,
        )
        source_artifact_value = self.correction_source_artifact(
            source_artifact=source_artifact,
            state=state,
            correction=correction,
        )
        material = {
            "contract": "casepath.correction-source-binding/1.0.0",
            "authority_adapter_id": self.adapter_id,
            "target_artifact_receipt_sha256": source_artifact.receipt_sha256,
            "target_observation_sha256": (
                source_artifact.observation.observation_sha256
            ),
            "target_fact_id": source_artifact.observation.fact_id,
            "target_evidence_item_id": source_artifact.observation.evidence_item_id,
            "correction_id": correction.correction_id,
            "correction_source_ref_sha256": digest_value(
                correction.source_ref.model_dump(mode="json")
            ),
            "correction_source_refs_sha256": digest_value(
                [ref.model_dump(mode="json") for ref in _validated_refs(self._packet(source_artifact))]
            ),
            "correction_source_artifact_sha256": digest_value(
                source_artifact_value
            ),
        }
        return {**material, "binding_sha256": digest_value(material)}

    def correction_source_artifact(
        self, *, source_artifact: ToolArtifactReceipt, state: Any, correction: Any
    ) -> dict[str, Any]:
        del state
        packet = self._packet(source_artifact)
        item = _source_artifact_map(packet).get(correction.source_ref.source_id)
        if item is None:
            raise ClaimLoopError("native correction source artifact is absent")
        return deepcopy(item)

    def correction_source_refs(
        self, *, source_artifact: ToolArtifactReceipt, state: Any, correction: Any
    ) -> list[dict[str, Any]]:
        del state
        refs = _validated_refs(self._packet(source_artifact))
        if not refs or refs[0] != correction.source_ref:
            raise ClaimLoopError("native correction source reference set changed")
        return [ref.model_dump(mode="json") for ref in refs]

    def observable_artifact_for_correction_source(
        self, *, source: ClaimSourceRef, correction: Any
    ) -> dict[str, Any]:
        del correction
        with self._lock:
            packets = list(self._staged.values())
        matches: list[dict[str, Any]] = []
        for packet in packets:
            refs = _validated_refs(packet)
            if refs and refs[0] == source:
                item = _source_artifact_map(packet).get(source.source_id)
                if item is not None:
                    matches.append(item)
        if len(matches) != 1:
            raise ClaimLoopError("native correction source registry is ambiguous")
        return deepcopy(matches[0])


class NativeSourceSetInterpreterV1:
    implementation_id = "casepath.native-source-set-interpreter/1.0.0"

    @property
    def implementation_source_sha256(self) -> str:
        return _module_sha256()

    @staticmethod
    def _need_binding(state: Any, need_id: str) -> dict[str, Any]:
        package = state.accepted_artifacts.get("observable_package")
        roster = package.get("native_need_roster") if isinstance(package, Mapping) else None
        matches = [row for row in roster or [] if row.get("need_id") == need_id]
        if len(matches) != 1:
            raise ClaimLoopError("native need is outside the accepted provisional roster")
        return dict(matches[0])

    def interpret(
        self,
        *,
        action: EvidenceAction,
        state: Any,
        acquisition: AcquisitionReceiptV1,
    ) -> CanonicalFactInterpretationV1:
        packet = _closed_packet(acquisition.sanitized_content or "")
        _validated_role_evidence(packet)
        binding = self._need_binding(state, str(packet["need_id"]))
        if (
            packet["claim_id"] != state.claim_id
            or binding["fact_id"] != action.fact_id
            or binding["evidence_item_id"] != action.evidence_item_id
            or binding["description"] != packet["description"]
        ):
            raise ClaimLoopError("native answer is not bound to the selected inquiry")
        refs = _validated_refs(packet)
        known = packet["state"] == "received"
        conflicting = packet["state"] == "contested"
        observation_material = {
            "contract": "casepath.claim-observation/1.0.0",
            "observation_id": "observation."
            + digest_value(
                {
                    "acquisition_receipt_sha256": acquisition.receipt_sha256,
                    "proposal_item_sha256": packet["proposal_item_sha256"],
                    "action_sha256": action.action_sha256,
                }
            ),
            "fact_id": action.fact_id,
            "evidence_item_id": action.evidence_item_id,
            "value": packet["answer"],
            "fact_state": "known" if known else "conflicting" if conflicting else "unknown",
            "normalized_value": "observed" if known else None,
            "explanation": (
                "Fallible source-relative answer admitted from a qualified native "
                "proposal after every cited span was resolved by the server."
            ),
            "evidence_status": (
                "provided_sufficient" if known else "provided_insufficient"
            ),
            "source_refs": [ref.model_dump(mode="json") for ref in refs],
            "observed_at": packet["observed_at"],
        }
        observation = ClaimObservation.model_validate(
            {
                **observation_material,
                "observation_sha256": digest_value(observation_material),
            }
        )
        prior_fact = next(
            row for row in state.facts if row.get("fact_id") == action.fact_id
        )
        interpretation_material = {
            "contract": "casepath.canonical-fact-interpretation/1.2.0",
            "action_id": action.action_id,
            "action_sha256": action.action_sha256,
            "fact_id": action.fact_id,
            "evidence_item_id": action.evidence_item_id,
            "acquisition_receipt_sha256": acquisition.receipt_sha256,
            "raw_artifact_sha256": acquisition.receipt_sha256,
            "prior_fact_sha256": digest_value(prior_fact),
            "assertion_catalog_sha256": packet["proposal_item_sha256"],
            "selected_assertion_id": "native-need." + str(packet["need_id"]),
            "observation": observation.model_dump(mode="json"),
            "implementation": self.implementation_id,
            "implementation_source_sha256": self.implementation_source_sha256,
            "model_calls": 0,
            "provider_calls": 0,
            "provider_credentials_read": False,
            "cost_usd": 0.0,
        }
        return CanonicalFactInterpretationV1.model_validate(
            {
                **interpretation_material,
                "receipt_sha256": digest_value(interpretation_material),
            }
        )

    def validate_interpreted_source_binding(self, **kwargs: Any) -> None:
        observation = kwargs["observation"]
        acquisition = kwargs["acquisition"]
        expected = self.interpret(
            action=kwargs["action"], state=kwargs["state"], acquisition=acquisition
        ).observation
        if observation != expected:
            raise ClaimLoopError("native source-set observation changed")

    def validate_observation_source_binding(self, **kwargs: Any) -> None:
        receipt = kwargs["receipt"]
        expected = self.interpret(
            action=kwargs["action"],
            state=kwargs["state"],
            acquisition=kwargs["acquisition"],
        )
        if receipt.interpretation != expected or receipt.observation != expected.observation:
            raise ClaimLoopError("native source-set receipt changed")

    @staticmethod
    def authority_binding_for_interpretation(
        interpretation: CanonicalFactInterpretationV1,
    ) -> dict[str, Any]:
        """Return the closed source-set sidecar journaled with the observation.

        Workspace-owned ClaimLoops fail closed unless the artifact interpreter can
        verify the evidence sidecar during the same journal transaction.  The
        native boundary has no external authority service: its authority is the
        server-resolved set of admitted source references captured by the signed
        interpretation receipt.
        """
        observation = interpretation.observation
        material = {
            "contract": "casepath.native-source-set-authority/1.0.0",
            "adapter_id": NATIVE_SOURCE_SET_ADAPTER_ID,
            "interpretation_receipt_sha256": interpretation.receipt_sha256,
            "observation_sha256": observation.observation_sha256,
            "source_refs_sha256": digest_value(
                [ref.model_dump(mode="json") for ref in observation.source_refs]
            ),
        }
        return {**material, "binding_sha256": digest_value(material)}

    def validate_recorded_authority_event(self, event: Any) -> None:
        if event.event_type != "OBSERVATION_INGESTED":
            return
        artifact = event.command.get("tool_artifact_receipt")
        if not isinstance(artifact, Mapping):
            raise ClaimLoopError("native authority artifact is absent")
        if artifact.get("adapter_id") != NATIVE_SOURCE_SET_ADAPTER_ID:
            raise ClaimLoopError("native authority adapter identity changed")
        try:
            interpretation = CanonicalFactInterpretationV1.model_validate(
                artifact.get("interpretation")
            )
            packet = _closed_packet(str(artifact.get("sanitized_content", "")))
            _validated_role_evidence(packet)
            refs = _validated_refs(packet)
        except (TypeError, ValueError) as exc:
            raise ClaimLoopError("native authority artifact is invalid") from exc
        if tuple(interpretation.observation.source_refs) != refs:
            raise ClaimLoopError("native authority source set differs")
        expected = self.authority_binding_for_interpretation(interpretation)
        if event.command.get("evidence_authority_binding") != expected:
            raise ClaimLoopError("native journal authority chain differs")

    @staticmethod
    def observable_artifact_for_source_ref(
        *, source: ClaimSourceRef, artifact: ToolArtifactReceipt
    ) -> dict[str, Any]:
        packet = _closed_packet(artifact.sanitized_content)
        _validated_role_evidence(packet)
        item = _source_artifact_map(packet).get(source.source_id)
        if item is None:
            raise ClaimLoopError("native source artifact is absent")
        return item


def _safe_token(value: str) -> str:
    return digest_value(value)[:24]


def _view_artifacts(material: Mapping[str, Any]) -> list[dict[str, Any]]:
    document = material["source_document"]
    raw_by_id = {
        row["artifact_id"]: row["raw_sha256"] for row in material["source_receipts"]
    }
    artifacts: list[dict[str, Any]] = []
    for view in document["text_views"]:
        text = "".join(unit["text"] for unit in view["units"])
        parent = view["source_id"]
        raw_sha = raw_by_id.get(parent)
        if not is_sha256(raw_sha):
            raise NativeClaimLoopBridgeError("native view lacks raw-byte identity")
        view_sha = digest_text(text)
        artifacts.append(
            {
                "artifact_id": view["view_id"],
                "filename": view["view_id"] + ".txt",
                "media_type": "text/plain; charset=utf-8",
                "received_at": view["first_observed_at"],
                "page_count": 1,
                "sha256": view_sha,
                "extracted_pages": [{"page": 1, "text": text}],
                "parent_artifact_id": parent,
                "parent_artifact_sha256": raw_sha,
            }
        )
    return artifacts


def _claim_ref(pointer: Mapping[str, Any], material: Mapping[str, Any]) -> dict[str, Any]:
    if pointer.get("kind") != "text":
        raise NativeClaimLoopBridgeError(
            "this ClaimLoop contract admits exact text spans; image-only meaning remains provisional"
        )
    return _pointer_claim_ref(
        pointer, str(material["source_prefix_sha256"])
    ).model_dump(mode="json")


def _revision_pointer_map(material: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    proposal = material.get("provisional_proposal")
    needs = proposal.get("needs") if isinstance(proposal, Mapping) else None
    if not isinstance(needs, list):
        raise NativeClaimLoopBridgeError("native revision has no proposal needs")
    result: dict[str, Mapping[str, Any]] = {}
    for need in needs:
        if not isinstance(need, Mapping):
            raise NativeClaimLoopBridgeError("native revision need is invalid")
        for pointer in [*need.get("warrants", []), *need.get("evidence", [])]:
            if not isinstance(pointer, Mapping) or not isinstance(pointer.get("ref"), str):
                raise NativeClaimLoopBridgeError("native revision pointer is invalid")
            existing = result.get(str(pointer["ref"]))
            identity = {key: value for key, value in pointer.items() if key != "role"}
            existing_identity = (
                {key: value for key, value in existing.items() if key != "role"}
                if existing is not None
                else None
            )
            if existing_identity is not None and existing_identity != identity:
                raise NativeClaimLoopBridgeError("native revision pointer identity collides")
            result[str(pointer["ref"])] = pointer
    return result


def _revision_source_ref(
    source_ref: str,
    *,
    material: Mapping[str, Any],
    pointers: Mapping[str, Mapping[str, Any]],
) -> ClaimSourceRef:
    pointer = pointers.get(source_ref)
    if pointer is None:
        raise NativeClaimLoopBridgeError("native revision cites an unavailable source ref")
    ref = ClaimSourceRef.model_validate(_claim_ref(pointer, material))
    artifacts = {row["artifact_id"]: row for row in _view_artifacts(material)}
    artifact = artifacts.get(ref.source_id)
    pages = artifact.get("extracted_pages") if isinstance(artifact, Mapping) else None
    text = pages[0].get("text") if isinstance(pages, list) and len(pages) == 1 else None
    if (
        artifact is None
        or artifact.get("sha256") != ref.source_sha256
        or not isinstance(text, str)
        or ref.text_start is None
        or ref.text_end is None
        or text[ref.text_start : ref.text_end] != ref.sanitized_excerpt
    ):
        raise NativeClaimLoopBridgeError("native revision source ref differs from admitted bytes")
    return ref


def _material_image_receipt(
    pointer: Mapping[str, Any], material: Mapping[str, Any]
) -> dict[str, Any]:
    matches = [
        row
        for row in material.get("native_image_receipts", [])
        if isinstance(row, Mapping) and row.get("image_id") == pointer.get("ref")
    ]
    view_matches = [
        row
        for row in material.get("source_document", {}).get("image_views", [])
        if isinstance(row, Mapping)
        and row.get("ref") == pointer.get("ref")
        and row.get("source_id") == pointer.get("source_id")
        and row.get("view_id") == pointer.get("view_id")
        and row.get("page_index") == pointer.get("page_index")
        and row.get("first_observed_at") == pointer.get("first_observed_at")
    ]
    parent_matches = [
        row
        for row in material.get("source_receipts", [])
        if isinstance(row, Mapping)
        and row.get("artifact_id") == pointer.get("source_id")
        and row.get("raw_sha256") == pointer.get("raw_artifact_sha256")
    ]
    if len(matches) != 1 or len(view_matches) != 1 or len(parent_matches) != 1:
        raise NativeClaimLoopBridgeError(
            "native image context is outside the admitted source prefix"
        )
    receipt = deepcopy(dict(matches[0]))
    try:
        _validate_image_receipt(pointer, receipt)
    except ClaimLoopError as exc:
        raise NativeClaimLoopBridgeError(str(exc)) from exc
    return receipt


def _role_preserving_packet_fields(
    *, need: Mapping[str, Any], material: Mapping[str, Any], mutation_kind: str
) -> dict[str, Any]:
    evidence = need.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        raise NativeClaimLoopBridgeError("native need lacks evidence")
    semantic_roles = (
        {"support", "contrary"}
        if mutation_kind == "observation"
        else {"correction"}
    )
    semantic_refs: list[dict[str, Any]] = []
    context_refs: list[dict[str, Any]] = []
    image_receipts: list[dict[str, Any]] = []
    selected_view_ids: set[str] = set()
    selected_image_parent_ids: set[str] = set()
    for pointer in evidence:
        if not isinstance(pointer, Mapping):
            raise NativeClaimLoopBridgeError("native evidence pointer is invalid")
        kind = pointer.get("kind")
        role = pointer.get("role")
        if kind == "text":
            ref = _claim_ref(pointer, material)
            selected_view_ids.add(ref["source_id"])
            if role in semantic_roles:
                semantic_refs.append(ref)
            else:
                context_refs.append(ref)
        elif kind == "native_image":
            if mutation_kind == "correction" and role != "context":
                raise NativeClaimLoopBridgeError(
                    "native correction requires exact text correction evidence"
                )
            if role not in {"context", "support", "contrary"}:
                raise NativeClaimLoopBridgeError(
                    "native image evidence role is invalid"
                )
            image_receipts.append(_material_image_receipt(pointer, material))
            selected_image_parent_ids.add(str(pointer.get("source_id")))
        else:
            raise NativeClaimLoopBridgeError("native evidence kind is invalid")
    if not semantic_refs:
        raise NativeClaimLoopBridgeError(
            "native answer has no text source with a fact-bearing role"
        )
    artifacts = [
        row
        for row in _view_artifacts(material)
        if row["artifact_id"] in selected_view_ids
        or row["parent_artifact_id"] in selected_image_parent_ids
    ]
    if {row["artifact_id"] for row in artifacts} != selected_view_ids:
        raise NativeClaimLoopBridgeError("native evidence text view is absent")
    return {
        "mutation_kind": mutation_kind,
        "source_refs": semantic_refs,
        "context_source_refs": context_refs,
        "native_image_receipts": image_receipts,
        "evidence": deepcopy(evidence),
        "source_artifacts": artifacts,
        # The server fills this after it has loaded the durable target under
        # an expected-parent CAS. Actor-assigned roles cannot certify that an
        # old source fact was previously extracted.
        "correction_transition_binding": None,
    }


def build_native_provisional_playbook_v1(
    *, claim_id: str, material: Mapping[str, Any]
) -> tuple[PlaybookTemplate, dict[str, Any], dict[str, Any]]:
    proposal = material.get("provisional_proposal")
    needs = proposal.get("needs") if isinstance(proposal, Mapping) else None
    if not isinstance(needs, list) or not needs or len(needs) > 16:
        raise NativeClaimLoopBridgeError("qualified native proposal has no bounded need roster")
    need_ids = [row.get("need_id") for row in needs if isinstance(row, Mapping)]
    if len(need_ids) != len(needs) or len(need_ids) != len(set(need_ids)):
        raise NativeClaimLoopBridgeError("native need identities are invalid")
    artifacts = _view_artifacts(material)
    facts: list[dict[str, Any]] = []
    items: list[dict[str, Any]] = []
    nodes: list[dict[str, Any]] = []
    gap_nodes: list[dict[str, Any]] = []
    edges: list[dict[str, str]] = []
    route_steps: list[dict[str, Any]] = []
    decision_options: dict[str, dict[str, str]] = {}
    fail_closed: dict[str, str] = {}
    evidence_nodes: dict[str, list[str]] = {}
    evidence_facts: dict[str, str] = {}
    need_roster: list[dict[str, Any]] = []
    for index, need in enumerate(needs):
        state = need.get("state")
        if state not in _NATIVE_NEED_STATES:
            raise NativeClaimLoopBridgeError("native need state is invalid")
        until = _validated_native_until(need.get("until"))
        if until is not None and state != "pending":
            raise NativeClaimLoopBridgeError(
                "native need until requires pending state"
            )
        token = _safe_token(str(need["need_id"]))
        node_id = "native_need." + token
        gap_id = "native_gap." + token
        fact_id = "fact.native." + token
        item_id = "native_evidence." + token
        decision_key = "native." + token + ".state"
        next_id = (
            "native_need." + _safe_token(str(needs[index + 1]["need_id"]))
            if index + 1 < len(needs)
            else "native_inquiry.review"
        )
        unresolved = "unresolved"
        observed = "observed"
        decision_options[decision_key] = {
            unresolved: decision_key + ".unresolved",
            observed: decision_key + ".observed",
        }
        fail_closed[decision_key] = unresolved
        warrants = need.get("warrants")
        if not isinstance(warrants, list) or not warrants:
            raise NativeClaimLoopBridgeError("native need lacks an original-source warrant")
        seed_refs = []
        for row in warrants:
            native_ref = _claim_ref(row, material)
            seed_refs.append(
                {
                    "artifact_id": native_ref["source_id"],
                    "artifact_sha256": native_ref["source_sha256"],
                    "locator_kind": "text_quote",
                    "page": native_ref["page"],
                    "excerpt": native_ref["sanitized_excerpt"],
                    "agent": "Fallible native inquiry projector",
                }
            )
        facts.append(
            {
                "fact_id": fact_id,
                "label": str(need["description"]),
                "value": "The source-derived inquiry has no admitted answer.",
                "state": "unknown",
                "explanation": "The native reader proposal is fallible and has not changed product facts.",
                "source_refs": seed_refs,
                "confidence": 1.0,
                "controls_process": True,
                "decision_key": decision_key,
                "normalized_value": unresolved,
                "decision_value": decision_options[decision_key][unresolved],
                "semantic_role": fact_id,
            }
        )
        items.append(
            {
                "item_id": item_id,
                "title": str(need["description"]),
                "status": "missing",
                "node_id": node_id,
                "fact_id": fact_id,
                "why": "Resolve this source-warranted provisional inquiry.",
                "legal_basis_ids": [],
                "artifact_ids": [],
                "acceptable_alternatives": [],
                "applies_when": "always",
                "required_level": "mandatory",
                "current_path": index == 0,
                "node_ids": [node_id],
                "bounded_tool_id": NATIVE_SOURCE_SET_ADAPTER_ID,
                "max_observed_attempts": 2,
            }
        )
        nodes.append(
            {
                "node_id": node_id,
                "title": str(need["description"]),
                "question": str(need["description"]),
                "state": "future",
                "answer": "Not reached",
                "why": "Source-warranted provisional inquiry; no legal sufficiency claim.",
                "kind": "decision",
                "main_spine": True,
                "fact_ids": [fact_id],
                "legal_source_ids": [],
                "evidence_requirement_ids": [item_id],
                "branches": [
                    {"branch_id": node_id + ".unresolved", "target": gap_id},
                    {"branch_id": node_id + ".observed", "target": next_id},
                ],
                "activation": "always",
            }
        )
        gap_nodes.append(
            {
                "node_id": gap_id,
                "title": "Evidence still required",
                "question": str(need["description"]),
                "state": "future",
                "answer": "Not reached",
                "why": "No source-set answer has been admitted.",
                "kind": "evidence_gap",
                "main_spine": False,
                "fact_ids": [],
                "legal_source_ids": [],
                "evidence_requirement_ids": [],
                "branches": [],
                "activation": "always",
            }
        )
        edges.extend(
            [
                {"source": node_id, "target": gap_id, "state": "possible"},
                {"source": node_id, "target": next_id, "state": "possible"},
            ]
        )
        route_steps.append(
            {
                "node_id": node_id,
                "decision_key": decision_key,
                "transitions": {
                    decision_options[decision_key][unresolved]: {
                        "kind": "stop",
                        "target_node_id": gap_id,
                        "selected_branch_id": node_id + ".unresolved",
                        "append_target": True,
                    },
                    decision_options[decision_key][observed]: {
                        "kind": "jump" if index + 1 < len(needs) else "stop",
                        "target_node_id": next_id,
                        "selected_branch_id": node_id + ".observed",
                        "append_target": True,
                    },
                },
            }
        )
        evidence_nodes[item_id] = [node_id]
        evidence_facts[item_id] = fact_id
        need_roster.append(
            {
                "need_id": str(need["need_id"]),
                "description": str(need["description"]),
                "state": state,
                "until": until,
                "fact_id": fact_id,
                "evidence_item_id": item_id,
                "proposed_action": validated_native_proposed_action_v1(
                    need.get("proposed_action")
                ),
            }
        )
    review_node = {
        "node_id": "native_inquiry.review",
        "title": "Review the provisional source-relative answers",
        "question": "Review without treating completion as legal readiness.",
        "state": "future",
        "answer": "Not reached",
        "why": "All constructed inquiry steps have source-relative answers.",
        "kind": "process",
        "main_spine": True,
        "fact_ids": [],
        "legal_source_ids": [],
        "evidence_requirement_ids": [],
        "branches": [],
        "activation": "always",
    }
    process_nodes = [*nodes, review_node, *gap_nodes]
    process = {
        "claim_id": claim_id,
        "nodes": process_nodes,
        "edges": edges,
        "main_spine": [row["node_id"] for row in nodes] + ["native_inquiry.review"],
        "current_node": nodes[0]["node_id"],
        "selected_path": [],
        "current_overlay": {},
    }
    record = {"facts": facts, "process": process, "checklist": {"items": items}}
    catalog = {
        "supported_claim_ids": [claim_id],
        "claim_sha256_by_id": {claim_id: digest_value(record)},
        "decision_options": decision_options,
        "process_node_ids": [row["node_id"] for row in process_nodes],
        "process_edge_pairs": [[row["source"], row["target"]] for row in edges],
        "process_fact_ids_by_claim": {claim_id: [row["fact_id"] for row in facts]},
        "evidence_item_ids_by_claim": {claim_id: [row["item_id"] for row in items]},
        "evidence_node_ids": evidence_nodes,
        "evidence_fact_ids_by_claim": {claim_id: evidence_facts},
        "evidence_artifact_ids_by_claim": {claim_id: []},
        "base_evidence_status_by_claim": {
            claim_id: {row["item_id"]: "missing" for row in items}
        },
        "legal_registry_version": "native-provisional-no-legal-authority/1.0.0",
        "legal_sources_sha256": digest_value([]),
        "same_six_agent_stategraph": True,
        "fail_closed_normalized_values": fail_closed,
        "route_program": {"start_path": [], "steps": route_steps},
        "process_rendering_profile": {
            "answer_by_node": {
                nodes[index]["node_id"]: {
                    decision_options[list(decision_options)[index]]["unresolved"]: "Unresolved",
                    decision_options[list(decision_options)[index]]["observed"]: "Source-relative answer observed",
                }
                for index in range(len(nodes))
            },
            "blocked_node_ids": [],
            "loop_edge_pairs": [],
            "future_edge_sources": [],
        },
        "evidence_projection_mode": "current_path_only_v1",
        "evidence_artifact_capabilities": {
            row["item_id"]: ["native_source_set"] for row in items
        },
        "maximum_controlling_facts": len(facts),
        "materializer_mode": "declarative_cycle_v1",
        "declarative_records": {claim_id: record},
    }
    template = PlaybookTemplate.build(
        template_id="casepath.native-provisional." + _safe_token(claim_id),
        template_version="1.0.0",
        catalog=catalog,
    )
    proposal_artifact_id = "native-proposal." + str(proposal["proposal_sha256"])
    proposal_subject = "Provisional source-warranted inquiry"
    proposal_body = "Native proposal remains fallible and source-relative."
    proposal_text = proposal_subject + "\n" + proposal_body
    proposal_artifact = {
        "artifact_id": proposal_artifact_id,
        "filename": proposal_artifact_id + ".txt",
        "media_type": "text/plain; charset=utf-8",
        "received_at": proposal["observed_at"],
        "page_count": 1,
        "sha256": digest_text(proposal_text),
        "extracted_pages": [{"page": 1, "text": proposal_text}],
        "parent_artifact_id": proposal_artifact_id,
        "parent_artifact_sha256": digest_text(proposal_text),
    }
    initial_source_ids = {
        source["artifact_id"] for fact in facts for source in fact["source_refs"]
    }
    initial_source_artifacts = [
        artifact for artifact in artifacts if artifact["artifact_id"] in initial_source_ids
    ]
    package = {
        "claim_id": claim_id,
        "customer_message": {
            "artifact_id": proposal_artifact_id,
            "subject": proposal_subject,
            "body": proposal_body,
        },
        "artifacts": [proposal_artifact, *initial_source_artifacts],
        "native_need_roster": need_roster,
        "native_proposal_receipt": {
            "cycle_id": material["cycle_id"],
            "proposal_sha256": proposal["proposal_sha256"],
            "source_prefix_sha256": material["source_prefix_sha256"],
            "authority": "fallible_proposal_only",
        },
    }
    legal = {
        "contract": "casepath.native-provisional-legal-context/1.0.0",
        "registry_version": catalog["legal_registry_version"],
        "sources": [],
    }
    return template, package, legal


def _observation_packet(
    *, claim_id: str, material: Mapping[str, Any], need_id: str
) -> dict[str, Any]:
    proposal = material["provisional_proposal"]
    matches = [row for row in proposal["needs"] if row["need_id"] == need_id]
    if len(matches) != 1:
        raise NativeClaimLoopBridgeError("native cycle does not contain the selected need")
    need = matches[0]
    if not isinstance(need.get("answer"), str) or not need["answer"].strip():
        raise NativeClaimLoopBridgeError("native need has no source-relative answer")
    evidence_fields = _role_preserving_packet_fields(
        need=need, material=material, mutation_kind="observation"
    )
    packet = {
        "contract": PACKET_CONTRACT,
        "claim_id": claim_id,
        "need_id": need_id,
        "description": need["description"],
        "answer": need["answer"],
        "state": need["state"],
        "observed_at": proposal["observed_at"],
        "source_prefix_sha256": proposal["source_prefix_sha256"],
        "proposal_item_sha256": need["proposal_item_sha256"],
        "proposed_action": validated_native_proposed_action_v1(
            need.get("proposed_action")
        ),
        **evidence_fields,
    }
    _validated_role_evidence(
        _closed_packet(canonical_json_bytes(packet).decode("utf-8"))
    )
    return packet


def _correction_packet(
    *, claim_id: str, material: Mapping[str, Any], need_id: str
) -> dict[str, Any]:
    """Separate correction-role spans from verified supporting context."""
    proposal = material["provisional_proposal"]
    matches = [row for row in proposal["needs"] if row["need_id"] == need_id]
    if len(matches) != 1:
        raise NativeClaimLoopBridgeError("native correction lacks the selected need")
    need = matches[0]
    evidence = need.get("evidence")
    if not isinstance(need.get("answer"), str) or not need["answer"].strip():
        raise NativeClaimLoopBridgeError("native correction lacks exact text evidence")
    correction_evidence = [
        row
        for row in evidence or []
        if isinstance(row, Mapping) and row.get("role") == "correction"
    ]
    if not correction_evidence or any(
        row.get("kind") != "text" for row in correction_evidence
    ):
        raise NativeClaimLoopBridgeError(
            "native correction lacks text evidence with correction role"
        )
    view_ids = {str(row.get("view_id")) for row in correction_evidence}
    if len(view_ids) != 1:
        raise NativeClaimLoopBridgeError(
            "native correction-role evidence must belong to one source view"
        )
    evidence_fields = _role_preserving_packet_fields(
        need=need, material=material, mutation_kind="correction"
    )
    if len({row["source_id"] for row in evidence_fields["source_refs"]}) != 1:
        raise NativeClaimLoopBridgeError("native correction source identity changed")
    packet = {
        "contract": PACKET_CONTRACT,
        "claim_id": claim_id,
        "need_id": need_id,
        "description": need["description"],
        "answer": need["answer"],
        "state": need["state"],
        "observed_at": proposal["observed_at"],
        "source_prefix_sha256": proposal["source_prefix_sha256"],
        "proposal_item_sha256": need["proposal_item_sha256"],
        "proposed_action": validated_native_proposed_action_v1(
            need.get("proposed_action")
        ),
        **evidence_fields,
    }
    _validated_role_evidence(
        _closed_packet(canonical_json_bytes(packet).decode("utf-8"))
    )
    return packet


_CORRECTION_RESULT_FIELD_NAMES = {
    "correction_source_ref",
    "source_change_kind",
    "prior_source_fact_replacement_established",
    "description_refined",
    "correction_role_ref_count",
    "context_text_ref_count",
    "context_image_ref_count",
    "supporting_image_ref_count",
    "provisional",
    "canonical_fact_certification",
    "legal_readiness_certification",
    "proposed_action",
}
_LEGACY_CORRECTION_RESULT_FIELD_NAMES = (
    _CORRECTION_RESULT_FIELD_NAMES - {"proposed_action"}
)


def _correction_request_identity(
    *,
    claim_id: str,
    loop_id: str,
    cycle_id: str,
    need_id: str,
    packet: Mapping[str, Any],
) -> dict[str, Any]:
    """Bind a client key to immutable source-cycle input, not mutable loop state."""

    return {
        "contract": "casepath.native-correction-request-identity/1.0.0",
        "claim_id": claim_id,
        "loop_id": loop_id,
        "cycle_id": cycle_id,
        "need_id": need_id,
        "source_prefix_sha256": packet["source_prefix_sha256"],
        "proposal_item_sha256": packet["proposal_item_sha256"],
        "correction_packet_sha256": digest_value(packet),
    }


def _correction_client_context(
    *, request_identity: Mapping[str, Any], result_fields: Mapping[str, Any]
) -> dict[str, Any]:
    fields = deepcopy(dict(result_fields))
    if set(fields) != _CORRECTION_RESULT_FIELD_NAMES:
        raise NativeClaimLoopBridgeError(
            "native correction replay fields are invalid"
        )
    payload = {
        "contract": "casepath.native-correction-client-context/1.0.0",
        "request_identity": deepcopy(dict(request_identity)),
        "result_fields": fields,
    }
    return {**payload, "context_sha256": digest_value(payload)}


def _validated_correction_client_context(
    value: Mapping[str, Any], *, request_identity: Mapping[str, Any]
) -> dict[str, Any]:
    context = deepcopy(dict(value))
    if set(context) != {
        "contract",
        "request_identity",
        "result_fields",
        "context_sha256",
    }:
        raise NativeClaimLoopBridgeError(
            "completed native correction context is not closed"
        )
    payload = {key: row for key, row in context.items() if key != "context_sha256"}
    fields = context.get("result_fields")
    if (
        context.get("contract")
        != "casepath.native-correction-client-context/1.0.0"
        or context.get("request_identity") != dict(request_identity)
        or context.get("context_sha256") != digest_value(payload)
        or not isinstance(fields, Mapping)
        or frozenset(fields)
        not in {
            frozenset(_CORRECTION_RESULT_FIELD_NAMES),
            frozenset(_LEGACY_CORRECTION_RESULT_FIELD_NAMES),
        }
    ):
        raise NativeClaimLoopBridgeError(
            "completed native correction context is invalid"
        )
    try:
        validated_native_proposed_action_v1(fields.get("proposed_action"))
    except ClaimLoopError as exc:
        raise NativeClaimLoopBridgeError(str(exc)) from exc
    return context


def _native_correction_result(
    *,
    claim_id: str,
    loop_id: str,
    cycle_id: str,
    need_id: str,
    correction_id: str,
    result_fields: Mapping[str, Any],
    claim_loop_response: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "contract": "casepath.native-claim-loop-bridge-result/1.0.0",
        "operation": "correct",
        "claim_id": claim_id,
        "cycle_id": cycle_id,
        "loop_id": loop_id,
        "need_id": need_id,
        "correction_id": correction_id,
        **deepcopy(dict(result_fields)),
        "claim_loop_response": deepcopy(dict(claim_loop_response)),
    }


class NativeClaimLoopBridgeV1:
    """Drive the existing ClaimLoop from server-recorded native cycles."""

    def __init__(
        self,
        *,
        native_material: Callable[[str, str], Mapping[str, Any]],
        claim_loop: ClaimLoopService,
        pipeline_router: DeterministicTemplateCyclePipelineRouter,
        adapter: NativeSourceSetAdapterV1,
        correction_adapter: NativeSourceCorrectionAdapterV1 | None = None,
        workspace_binding: Callable[[str], Mapping[str, Any]] | None = None,
    ) -> None:
        self.native_material = native_material
        self.claim_loop = claim_loop
        self.pipeline_router = pipeline_router
        self.adapter = adapter
        self.correction_adapter = correction_adapter
        self.workspace_binding = workspace_binding

    def ensure(
        self, *, claim_id: str, cycle_id: str, idempotency_key: str
    ) -> dict[str, Any]:
        material = dict(self.native_material(claim_id, cycle_id))
        template, package, legal = build_native_provisional_playbook_v1(
            claim_id=claim_id, material=material
        )
        binding = (
            dict(self.workspace_binding(claim_id))
            if self.workspace_binding is not None
            else None
        )
        if binding is not None:
            if (
                binding.get("claim_id") != claim_id
                or not isinstance(binding.get("loop_id"), str)
                or not isinstance(binding.get("create_idempotency_key"), str)
                or not isinstance(binding.get("workspace_binding"), Mapping)
            ):
                raise NativeClaimLoopBridgeError(
                    "native workspace loop binding is invalid"
                )
            package["workspace_binding"] = deepcopy(
                dict(binding["workspace_binding"])
            )
        pipeline = self.pipeline_router.for_template(template)
        with self.pipeline_router._source_write_scope():
            source_run_id = pipeline.create_declarative_source(
                claim_id,
                observable_package=package,
                legal_research=legal,
                session_id=WORKSPACE_CLAIM_LOOP_SESSION_ID,
            )
        created = self.claim_loop.create(
            session_id=WORKSPACE_CLAIM_LOOP_SESSION_ID,
            source_run_id=source_run_id,
            idempotency_key=(
                str(binding["create_idempotency_key"])
                if binding is not None
                else idempotency_key + ".create"
            ),
        )
        if binding is not None and created.get("loop_id") != binding["loop_id"]:
            raise NativeClaimLoopBridgeError(
                "native proposal did not enter the workspace ClaimLoop"
            )
        selected = self.claim_loop.select_action(
            session_id=WORKSPACE_CLAIM_LOOP_SESSION_ID,
            loop_id=str(created["loop_id"]),
            idempotency_key=(
                "workspace-select.native.initial."
                + str(binding["assessment_sha256"])[:24]
                if binding is not None
                else idempotency_key + ".select"
            ),
        )
        return {
            "contract": "casepath.native-claim-loop-bridge-result/1.0.0",
            "operation": "ensure",
            "claim_id": claim_id,
            "cycle_id": cycle_id,
            "loop_id": created["loop_id"],
            "proposal_sha256": material["provisional_proposal"]["proposal_sha256"],
            "provisional": True,
            "canonical_fact_certification": False,
            "legal_readiness_certification": False,
            "claim_loop_response": selected,
        }

    def record_proposal_revision(
        self,
        *,
        claim_id: str,
        loop_id: str,
        prior_cycle_id: str,
        cycle_id: str,
        revision_packet: Mapping[str, Any],
        idempotency_key: str,
    ) -> dict[str, Any]:
        """Journal a later fallible proposal without creating fact observations.

        ``revision_packet`` is the actor's public three-array replan output.  It
        must disposition every action in the accepted initial proposal.  The
        bridge resolves all cited refs against the new cycle's server-observed
        bytes before the service appends the revision under a state CAS.
        """

        if set(revision_packet) != {
            "readings",
            "actions",
            "prior_action_dispositions",
        }:
            raise NativeClaimLoopBridgeError("native revision packet fields are not closed")
        readings = revision_packet.get("readings")
        actions = revision_packet.get("actions")
        dispositions = revision_packet.get("prior_action_dispositions")
        if (
            not isinstance(readings, list)
            or len(readings) > 16
            or not isinstance(actions, list)
            or len(actions) > 16
            or not isinstance(dispositions, list)
            or not dispositions
            or len(dispositions) > 16
        ):
            raise NativeClaimLoopBridgeError("native revision packet bounds are invalid")
        material = dict(self.native_material(claim_id, cycle_id))
        proposal = material.get("provisional_proposal")
        if (
            material.get("claim_id") != claim_id
            or material.get("cycle_id") != cycle_id
            or not isinstance(proposal, Mapping)
            or proposal.get("source_prefix_sha256") != material.get("source_prefix_sha256")
            or proposal.get("observed_at") != material.get("observed_at")
            or not is_sha256(proposal.get("proposal_sha256"))
            or not is_sha256(material.get("source_prefix_sha256"))
            or material.get("proposal_revision_packet_sha256")
            != digest_value(dict(revision_packet))
        ):
            raise NativeClaimLoopBridgeError("native revision cycle identity is invalid")
        request_identity = {
            "contract": "casepath.native-proposal-revision-request/1.0.0",
            "claim_id": claim_id,
            "loop_id": loop_id,
            "prior_cycle_id": prior_cycle_id,
            "cycle_id": cycle_id,
            "source_prefix_sha256": material["source_prefix_sha256"],
            "proposal_sha256": proposal["proposal_sha256"],
            "revision_packet_sha256": digest_value(dict(revision_packet)),
        }
        try:
            completed = self.claim_loop.replay_completed_native_proposal_revision_request(
                session_id=WORKSPACE_CLAIM_LOOP_SESSION_ID,
                loop_id=loop_id,
                idempotency_key=idempotency_key,
                request_identity=request_identity,
            )
        except ClaimLoopServiceError as exc:
            raise NativeClaimLoopBridgeError(str(exc)) from exc
        if completed is not None:
            replay_state = self.claim_loop.state(
                session_id=WORKSPACE_CLAIM_LOOP_SESSION_ID, loop_id=loop_id
            )
            matches = [
                value
                for value in replay_state.native_proposal_revisions
                if value.cycle_id == cycle_id
            ]
            if len(matches) != 1 or completed.get("loop_id") != loop_id:
                raise NativeClaimLoopBridgeError("completed native revision response is invalid")
            return {
                "contract": "casepath.native-claim-loop-bridge-result/1.0.0",
                "operation": "record_proposal_revision",
                "claim_id": claim_id,
                "cycle_id": cycle_id,
                "loop_id": loop_id,
                "revision_sha256": matches[0].revision_sha256,
                "provisional": True,
                "canonical_fact_certification": False,
                "legal_readiness_certification": False,
                "claim_loop_response": completed,
            }
        pointers = _revision_pointer_map(material)
        state = self.claim_loop.state(
            session_id=WORKSPACE_CLAIM_LOOP_SESSION_ID, loop_id=loop_id
        )
        if state.claim_id != claim_id or state.active_dispatch_sha256 is not None:
            raise NativeClaimLoopBridgeError("native revision target is unavailable")
        package = state.accepted_artifacts.get("observable_package")
        receipt = package.get("native_proposal_receipt") if isinstance(package, Mapping) else None
        roster = package.get("native_need_roster") if isinstance(package, Mapping) else None
        if not isinstance(receipt, Mapping) or not isinstance(roster, list):
            raise NativeClaimLoopBridgeError("native revision target lacks its accepted proposal")
        expected_prior_cycle = (
            state.native_proposal_revisions[-1].cycle_id
            if state.native_proposal_revisions
            else receipt.get("cycle_id")
        )
        if prior_cycle_id != expected_prior_cycle or cycle_id == prior_cycle_id:
            raise NativeClaimLoopBridgeError("native revision skips or repeats its prior cycle")
        prior_actions = [
            row for row in roster
            if isinstance(row, Mapping) and row.get("proposed_action") is not None
        ]
        indices = [row.get("prior_action_index") for row in dispositions if isinstance(row, Mapping)]
        if indices != list(range(len(prior_actions))):
            raise NativeClaimLoopBridgeError("native revision must disposition every prior action in order")
        revised = [row for row in dispositions if row.get("disposition") == "revised"]
        if len(revised) != len(actions):
            raise NativeClaimLoopBridgeError("native revised-action lineage is ambiguous")

        reading_records = []
        for index, row in enumerate(readings):
            legacy_fields = {
                "question", "answer", "source_refs", "state", "uncertainty"
            }
            if (
                not isinstance(row, Mapping)
                or frozenset(row) not in {
                    frozenset(legacy_fields),
                    frozenset({*legacy_fields, "until"}),
                }
            ):
                raise NativeClaimLoopBridgeError("native revision reading fields are invalid")
            answer = row.get("answer")
            model_state = row.get("state")
            if (
                not isinstance(row.get("question"), str)
                or not row["question"].strip()
                or (
                    answer is not None
                    and (not isinstance(answer, str) or not answer.strip())
                )
                or (answer is None and model_state != "pending")
                or model_state not in {"supported", "partial", "pending", "unresolved"}
                or not isinstance(row.get("source_refs"), list)
                or not row["source_refs"]
            ):
                raise NativeClaimLoopBridgeError("native revision reading is invalid")
            until = _validated_native_until(row.get("until"))
            if until is not None and model_state != "pending":
                raise NativeClaimLoopBridgeError(
                    "native revision until requires pending state"
                )
            refs = tuple(
                _revision_source_ref(str(value), material=material, pointers=pointers)
                for value in row["source_refs"]
            )
            reading_material = {
                "cycle_id": cycle_id,
                "wire_index": index,
                "question": row["question"],
                "answer": row["answer"],
                "state": row["state"],
                "source_ref_ids": [value.span_sha256 for value in refs],
            }
            if until is not None:
                reading_material["until"] = until
            stored_state = {
                "supported": "received",
                "partial": "partial",
                "pending": "pending",
                "unresolved": "uncertain",
            }[model_state]
            reading_records.append(
                {
                    "reading_id": "native-reading." + digest_value(reading_material),
                    "need_id": "native-snapshot-need." + digest_value(reading_material),
                    "description": row["question"],
                    "answer": row["answer"],
                    "state": stored_state,
                    "until": until,
                    "evidence": [
                        {"role": "support", "source_ref": value.model_dump(mode="json")}
                        for value in refs
                    ],
                    "proposal_item_sha256": digest_value(reading_material),
                }
            )

        action_records = []
        for index, row in enumerate(actions):
            if not isinstance(row, Mapping) or set(row) != {
                "audience", "purpose", "requested_contents", "source_warrant_refs"
            }:
                raise NativeClaimLoopBridgeError("native revision action fields are invalid")
            proposed = validated_native_proposed_action_v1(
                {
                    "audience": row.get("audience"),
                    "enabled": True,
                    "requested_contents": row.get("requested_contents"),
                }
            )
            if proposed is None or not isinstance(row.get("purpose"), str) or not row["purpose"].strip():
                raise NativeClaimLoopBridgeError("native revision action is invalid")
            raw_refs = row.get("source_warrant_refs")
            if not isinstance(raw_refs, list) or not raw_refs:
                raise NativeClaimLoopBridgeError("native revision action lacks warrants")
            refs = tuple(
                _revision_source_ref(str(value), material=material, pointers=pointers)
                for value in raw_refs
            )
            action_material = {
                "cycle_id": cycle_id,
                "action_index": index,
                "purpose": row["purpose"],
                "proposed_action": proposed,
                "source_ref_ids": [value.span_sha256 for value in refs],
            }
            action_records.append(
                {
                    "action_id": "native-action." + digest_value(action_material),
                    "action_index": index,
                    "purpose": row["purpose"],
                    "audience": proposed["audience"],
                    "requested_contents": proposed["requested_contents"],
                    "source_warrant_refs": [value.model_dump(mode="json") for value in refs],
                }
            )

        disposition_records = []
        revised_cursor = 0
        for index, row in enumerate(dispositions):
            if not isinstance(row, Mapping) or set(row) != {
                "disposition", "prior_action_index", "reason", "source_refs"
            }:
                raise NativeClaimLoopBridgeError("native action disposition fields are invalid")
            disposition = row.get("disposition")
            if (
                disposition not in {"revised", "retired"}
                or row.get("prior_action_index") != index
                or not isinstance(row.get("reason"), str)
                or not row["reason"].strip()
                or not isinstance(row.get("source_refs"), list)
                or not row["source_refs"]
            ):
                raise NativeClaimLoopBridgeError("native action disposition is invalid")
            refs = tuple(
                _revision_source_ref(str(value), material=material, pointers=pointers)
                for value in row["source_refs"]
            )
            replacement = None
            if disposition == "revised":
                replacement = action_records[revised_cursor]["action_id"]
                revised_cursor += 1
            prior = prior_actions[index]
            disposition_records.append(
                {
                    "prior_action_index": index,
                    "prior_need_id": prior["need_id"],
                    "prior_fact_id": prior["fact_id"],
                    "prior_evidence_item_id": prior["evidence_item_id"],
                    "disposition": disposition,
                    "reason": row["reason"],
                    "source_refs": [value.model_dump(mode="json") for value in refs],
                    "replacement_action_id": replacement,
                }
            )

        revision_material = {
            "contract": "casepath.native-proposal-revision/1.0.0",
            "claim_id": claim_id,
            "loop_id": loop_id,
            "prior_cycle_id": prior_cycle_id,
            "cycle_id": cycle_id,
            "source_prefix_sha256": material["source_prefix_sha256"],
            "proposal_sha256": proposal["proposal_sha256"],
            "parent_revision": state.revision,
            "parent_state_sha256": state.state_sha256,
            "readings": reading_records,
            "actions": action_records,
            "action_dispositions": disposition_records,
            "provisional": True,
            "canonical_fact_effect": None,
            "readiness_effect": None,
            "recorded_at": proposal["observed_at"],
        }
        revision = NativeProposalRevisionV1.model_validate(
            {
                **revision_material,
                "revision_sha256": digest_value(revision_material),
            }
        )
        try:
            response = self.claim_loop.record_native_proposal_revision(
                session_id=WORKSPACE_CLAIM_LOOP_SESSION_ID,
                loop_id=loop_id,
                proposal_revision=revision.model_dump(mode="json"),
                request_identity=request_identity,
                idempotency_key=idempotency_key,
                expected_revision=state.revision,
            )
        except ClaimLoopServiceError as exc:
            raise NativeClaimLoopBridgeError(str(exc)) from exc
        return {
            "contract": "casepath.native-claim-loop-bridge-result/1.0.0",
            "operation": "record_proposal_revision",
            "claim_id": claim_id,
            "cycle_id": cycle_id,
            "loop_id": loop_id,
            "revision_sha256": revision.revision_sha256,
            "provisional": True,
            "canonical_fact_certification": False,
            "legal_readiness_certification": False,
            "claim_loop_response": response,
        }

    def observe(
        self,
        *,
        claim_id: str,
        loop_id: str,
        cycle_id: str,
        need_id: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        material = dict(self.native_material(claim_id, cycle_id))
        packet = _observation_packet(
            claim_id=claim_id, material=material, need_id=need_id
        )
        state = self.claim_loop.state(
            session_id=WORKSPACE_CLAIM_LOOP_SESSION_ID, loop_id=loop_id
        )
        action = state.selected_action
        if action is None:
            raise NativeClaimLoopBridgeError("ClaimLoop has no active inquiry action")
        package = state.accepted_artifacts.get("observable_package")
        roster = package.get("native_need_roster") if isinstance(package, Mapping) else []
        match = [row for row in roster if row["need_id"] == need_id]
        if len(match) != 1 or match[0]["fact_id"] != action.fact_id:
            raise NativeClaimLoopBridgeError("native need does not match the current action")
        self.adapter.stage(action.action_id, packet)
        try:
            response = self.claim_loop.advance(
                session_id=WORKSPACE_CLAIM_LOOP_SESSION_ID,
                loop_id=loop_id,
                idempotency_key=idempotency_key,
                adapter_id=NATIVE_SOURCE_SET_ADAPTER_ID,
                expected_revision=state.revision,
                request_context_sha256=digest_value(packet),
            )
        except ClaimLoopServiceError as exc:
            raise NativeClaimLoopBridgeError(str(exc)) from exc
        finally:
            self.adapter.unstage(action.action_id)
        return {
            "contract": "casepath.native-claim-loop-bridge-result/1.0.0",
            "operation": "observe",
            "claim_id": claim_id,
            "cycle_id": cycle_id,
            "loop_id": loop_id,
            "need_id": need_id,
            "source_set_size": len(packet["source_refs"]),
            "context_text_ref_count": len(packet.get("context_source_refs", [])),
            "context_image_ref_count": _packet_image_role_count(
                packet, {"context"}
            ),
            "supporting_image_ref_count": _packet_image_role_count(
                packet, {"support", "contrary"}
            ),
            "source_artifact_count": len(packet["source_artifacts"]),
            "parent_source_count": len(
                {row["parent_artifact_id"] for row in packet["source_artifacts"]}
            ),
            "provisional": True,
            "canonical_fact_certification": False,
            "legal_readiness_certification": False,
            "claim_loop_response": response,
        }

    def correct(
        self,
        *,
        claim_id: str,
        loop_id: str,
        cycle_id: str,
        need_id: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        if self.correction_adapter is None:
            raise NativeClaimLoopBridgeError("native correction adapter is unavailable")
        material = dict(self.native_material(claim_id, cycle_id))
        packet = _correction_packet(
            claim_id=claim_id, material=material, need_id=need_id
        )
        request_identity = _correction_request_identity(
            claim_id=claim_id,
            loop_id=loop_id,
            cycle_id=cycle_id,
            need_id=need_id,
            packet=packet,
        )
        try:
            completed = self.claim_loop.replay_completed_correction_request(
                session_id=WORKSPACE_CLAIM_LOOP_SESSION_ID,
                loop_id=loop_id,
                idempotency_key=idempotency_key,
                request_identity=request_identity,
            )
        except ClaimLoopServiceError as exc:
            raise NativeClaimLoopBridgeError(str(exc)) from exc
        if completed is not None:
            context = _validated_correction_client_context(
                completed["client_request_context"],
                request_identity=request_identity,
            )
            return _native_correction_result(
                claim_id=claim_id,
                loop_id=loop_id,
                cycle_id=cycle_id,
                need_id=need_id,
                correction_id=completed["correction_id"],
                result_fields=context["result_fields"],
                claim_loop_response=completed["response"],
            )
        state = self.claim_loop.state(
            session_id=WORKSPACE_CLAIM_LOOP_SESSION_ID, loop_id=loop_id
        )
        package = state.accepted_artifacts.get("observable_package")
        roster = package.get("native_need_roster") if isinstance(package, Mapping) else []
        matches = [row for row in roster if row.get("need_id") == need_id]
        if len(matches) != 1:
            raise NativeClaimLoopBridgeError("native correction target is not in the roster")
        fact_id = matches[0]["fact_id"]
        observations = [row for row in state.observations if row.fact_id == fact_id]
        if len(observations) != 1:
            raise NativeClaimLoopBridgeError(
                "native correction requires one prior admitted assertion"
            )
        target = observations[0]
        prior_ref_by_span = {
            _stable_span_identity(ref): ref for ref in target.source_refs
        }
        context_refs = _validated_ref_field(packet, "context_source_refs")
        retained_prior_refs = [
            prior_ref_by_span[identity]
            for identity in (_stable_span_identity(ref) for ref in context_refs)
            if identity in prior_ref_by_span
        ]
        transition = {
            "contract": "casepath.native-correction-transition-binding/1.0.0",
            "need_id": need_id,
            "prior_observation_sha256": target.observation_sha256,
            "prior_value_sha256": digest_text(target.value),
            "correction_pointer_ids": [
                row["pointer_id"]
                for row in packet["evidence"]
                if row.get("role") == "correction"
            ],
            "scope": "extend_prior_source_relative_answer",
            "source_change_kind": "answer_extension",
            "prior_source_fact_replacement_established": False,
            "retained_prior_source_ref_sha256s": [
                digest_value(ref.model_dump(mode="json"))
                for ref in retained_prior_refs
            ],
            "durable_inquiry_description_sha256": digest_text(
                str(matches[0]["description"])
            ),
            "proposal_description_sha256": digest_text(
                str(packet["description"])
            ),
            "description_relation": (
                "same_durable_need_id_with_refined_proposal_description"
            ),
        }
        packet["correction_transition_binding"] = {
            **transition,
            "binding_sha256": digest_value(transition),
        }
        _validated_role_evidence(
            _closed_packet(canonical_json_bytes(packet).decode("utf-8"))
        )
        artifacts = []
        for entry in state.projection_ledger:
            artifact = self.claim_loop.store.tool_artifact(
                entry.artifact_receipt_sha256
            )
            if artifact is not None and artifact.observation.observation_id == target.observation_id:
                artifacts.append(artifact)
        if len(artifacts) != 1:
            raise NativeClaimLoopBridgeError(
                "native correction target artifact is ambiguous"
            )
        artifact = artifacts[0]
        result_fields = {
            "correction_source_ref": packet["source_refs"][0],
            "source_change_kind": transition["source_change_kind"],
            "prior_source_fact_replacement_established": transition[
                "prior_source_fact_replacement_established"
            ],
            "description_refined": (
                transition["durable_inquiry_description_sha256"]
                != transition["proposal_description_sha256"]
            ),
            "correction_role_ref_count": len(packet["source_refs"]),
            "context_text_ref_count": len(packet.get("context_source_refs", [])),
            "context_image_ref_count": _packet_image_role_count(
                packet, {"context"}
            ),
            "supporting_image_ref_count": _packet_image_role_count(
                packet, {"support", "contrary"}
            ),
            "provisional": True,
            "canonical_fact_certification": False,
            "legal_readiness_certification": False,
            "proposed_action": validated_native_proposed_action_v1(
                packet.get("proposed_action")
            ),
        }
        client_request_context = _correction_client_context(
            request_identity=request_identity,
            result_fields=result_fields,
        )
        self.correction_adapter.stage(artifact.receipt_sha256, packet)
        try:
            correction = self.claim_loop.register_correction(
                session_id=WORKSPACE_CLAIM_LOOP_SESSION_ID,
                loop_id=loop_id,
                source_artifact_receipt_sha256=artifact.receipt_sha256,
                correction_adapter_id=self.correction_adapter.adapter_id,
                issued_at=str(packet["observed_at"]),
                expected_parent_state_sha256=state.state_sha256,
            )
            response = self.claim_loop.apply_correction(
                session_id=WORKSPACE_CLAIM_LOOP_SESSION_ID,
                loop_id=loop_id,
                correction_id=correction.correction_id,
                idempotency_key=idempotency_key,
                client_request_context=client_request_context,
            )
        except ClaimLoopServiceError as exc:
            raise NativeClaimLoopBridgeError(str(exc)) from exc
        finally:
            self.correction_adapter.unstage(artifact.receipt_sha256)
        return _native_correction_result(
            claim_id=claim_id,
            loop_id=loop_id,
            cycle_id=cycle_id,
            need_id=need_id,
            correction_id=correction.correction_id,
            result_fields=result_fields,
            claim_loop_response=response,
        )


__all__ = [
    "NATIVE_SOURCE_SET_ADAPTER_ID",
    "NativeClaimLoopBridgeError",
    "NativeClaimLoopBridgeV1",
    "NativeSourceSetAdapterV1",
    "NativeSourceSetInterpreterV1",
    "NativeSourceCorrectionAdapterV1",
    "build_native_provisional_playbook_v1",
]
