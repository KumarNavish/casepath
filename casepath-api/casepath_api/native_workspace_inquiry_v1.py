"""Recorded native-reader entry for one manifest-bound workspace trajectory.

This module is deliberately an opt-in development replay adapter.  It binds a
saved completion to the exact source bytes, image order, observation clock and
the model's own preceding proposal before exposing it to the workspace.  Model
proposals and source roles remain provisional; the adapter never establishes a
world fact, legal sufficiency, or certified readiness.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

from .claim_loop_contracts import ClaimSourceRef
from .foundation.common import digest_text, digest_value
from .provisional_inquiry_v1 import (
    InquiryError,
    InquiryJournal,
    InquiryService,
    source_assertion_from_view,
    validate_source_assertion,
)
from .workspace_corpus import PublicCorpus

NATIVE_RESEARCH_MODE = "recorded-replay-v1"
NATIVE_SOURCE_ADAPTER_ID = "casepath.native-workspace-recorded-source/1.0.0"
NATIVE_ENTRY_CONTRACT = "casepath.native-workspace-inquiry/1.0.0"
EXPECTED_CLAIM_ID = "clm_e262801f9368bc12"

CAPABILITIES = {
    "internal_review": {
        "capability_id": "casepath.internal-inquiry-review/1.0.0",
        "dispatch_mode": "internal_only",
    },
    "external_evidence_request": {
        "capability_id": "casepath.recorded-research-request-replay/1.0.0",
        "dispatch_mode": "recorded_research_replay_only",
    },
}


class NativeWorkspaceInquiryError(ValueError):
    pass


class NativeWorkspaceInquiryConflict(NativeWorkspaceInquiryError):
    pass


def _sha_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _sha(path: Path) -> str:
    return _sha_bytes(path.read_bytes())


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _load(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise NativeWorkspaceInquiryError(f"recorded JSON is unavailable: {path}") from exc


def _aware(value: object, name: str) -> datetime:
    if not isinstance(value, str):
        raise NativeWorkspaceInquiryError(f"{name} is not an aware timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise NativeWorkspaceInquiryError(f"{name} is not an aware timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise NativeWorkspaceInquiryError(f"{name} is not an aware timestamp")
    return parsed


def _message_identity(messages: list[dict[str, Any]]) -> str:
    """Identity of exactly model-visible text, image identities and image order.

    Native paths are transport locations and are deliberately excluded.  The
    receipt records both original and rebound message hashes so this exception
    is explicit rather than silently treating a copied path as the old input.
    """

    normalized: list[dict[str, Any]] = []
    for message in messages:
        content = message.get("content")
        if not isinstance(content, list):
            normalized.append(deepcopy(message))
            continue
        blocks = []
        for block in content:
            value = deepcopy(block)
            if value.get("type") == "image":
                value.pop("image_path", None)
            blocks.append(value)
        normalized.append({**deepcopy(message), "content": blocks})
    return _sha_bytes(_canonical(normalized))


def _model_prior(value: Mapping[str, Any]) -> list[dict[str, Any]]:
    fields = (
        "need_id", "description", "answer", "warrant_refs", "evidence", "state", "until"
    )
    needs = value.get("needs")
    if not isinstance(needs, list):
        raise NativeWorkspaceInquiryError("recorded reader output has no needs roster")
    result = []
    seen: set[str] = set()
    for row in needs:
        if not isinstance(row, dict) or any(field not in row for field in fields):
            raise NativeWorkspaceInquiryError("recorded reader row differs from the native contract")
        need_id = row["need_id"]
        if not isinstance(need_id, str) or not need_id or need_id in seen:
            raise NativeWorkspaceInquiryError("recorded reader need identity is invalid")
        seen.add(need_id)
        if row["state"] not in {
            "missing", "partial", "pending", "received", "contested", "conditional",
            "withdrawn", "uncertain",
        }:
            raise NativeWorkspaceInquiryError("recorded reader state is invalid")
        result.append({field: deepcopy(row.get(field)) for field in fields})
    return result


class RecordedNativeProviderV1:
    """Fail-closed adapter over a declared saved trajectory."""

    def __init__(self, manifest_path: Path, corpus: PublicCorpus) -> None:
        self.manifest_path = manifest_path.resolve()
        self.corpus = corpus
        self.manifest = _load(self.manifest_path)
        if (
            not isinstance(self.manifest, dict)
            or self.manifest.get("contract")
            != "casepath.recorded-native-workspace-trace/1.0.0"
            or self.manifest.get("claim_id") != EXPECTED_CLAIM_ID
            or self.manifest.get("research_mode") != NATIVE_RESEARCH_MODE
            or self.manifest.get("contains_expected_world_state") is not False
        ):
            raise NativeWorkspaceInquiryError("recorded provider manifest is invalid")
        calls = self.manifest.get("calls")
        sources = self.manifest.get("sources")
        if not isinstance(calls, list) or not isinstance(sources, list):
            raise NativeWorkspaceInquiryError("recorded provider manifest is incomplete")
        self.calls = {row.get("call_id"): deepcopy(row) for row in calls if isinstance(row, dict)}
        self.sources = {row.get("source_key"): deepcopy(row) for row in sources if isinstance(row, dict)}
        if len(self.calls) != len(calls) or len(self.sources) != len(sources):
            raise NativeWorkspaceInquiryError("recorded provider identities collide")
        required_calls = {"initial_read", "generic_refinement", "after_response", "after_correction", "correction_target"}
        if set(self.calls) != required_calls:
            raise NativeWorkspaceInquiryError("recorded provider call roster differs")
        self._verify_declared_files()

    def file_path(self, receipt: Mapping[str, Any]) -> Path:
        """Resolve one transport path relative to the closed trace package."""

        raw = receipt.get("path")
        if not isinstance(raw, str) or not raw:
            raise NativeWorkspaceInquiryError("recorded file path is absent")
        stated = Path(raw)
        if stated.is_absolute():
            return stated
        package_root = self.manifest_path.parent
        resolved = (package_root / stated).resolve()
        try:
            resolved.relative_to(package_root)
        except ValueError as exc:
            raise NativeWorkspaceInquiryError(
                "recorded relative path escapes its trace package"
            ) from exc
        return resolved

    def _verify_file_receipt(self, item: Mapping[str, Any]) -> None:
        if not {"path", "sha256", "size_bytes"} <= set(item):
            raise NativeWorkspaceInquiryError("recorded file receipt is incomplete")
        path = self.file_path(item)
        try:
            raw = path.read_bytes()
        except OSError as exc:
            raise NativeWorkspaceInquiryError(f"recorded file is unavailable: {path}") from exc
        if len(raw) != item["size_bytes"] or _sha_bytes(raw) != item["sha256"]:
            raise NativeWorkspaceInquiryError(f"recorded file identity differs: {path}")

    def _verify_declared_files(self) -> None:
        policy = self.manifest.get("trajectory_policy")
        if not isinstance(policy, dict):
            raise NativeWorkspaceInquiryError("trajectory policy receipt is absent")
        self._verify_file_receipt(policy)
        for collection in (self.manifest["sources"], self.manifest["calls"]):
            for row in collection:
                for field in (
                    "raw", "rendered", "input", "source_input", "output", "instruction", "stdin"
                ):
                    item = row.get(field)
                    if item is None:
                        continue
                    if (
                        not isinstance(item, dict)
                        or not {"path", "sha256", "size_bytes"} <= set(item)
                    ):
                        raise NativeWorkspaceInquiryError("recorded file receipt is incomplete")
                    self._verify_file_receipt(item)

    def _verify_source(self, source_key: str) -> dict[str, Any]:
        try:
            source = self.sources[source_key]
        except KeyError as exc:
            raise NativeWorkspaceInquiryError("provider requested an undeclared source") from exc
        authority = source.get("authority")
        if authority == "public_corpus":
            raw, row = self.corpus.artifact(EXPECTED_CLAIM_ID, source["artifact_id"])
            expected = source["raw"]
            if (
                row["sha256"] != expected["sha256"]
                or row["size_bytes"] != expected["size_bytes"]
                or row["media_type"] != expected["media_type"]
                or _sha_bytes(raw) != expected["sha256"]
            ):
                raise NativeWorkspaceInquiryError("public corpus source binding differs")
            raw_path = self.corpus.root / row["path"]
        elif authority == "recorded_server_artifact":
            expected = source["raw"]
            raw_path = self.file_path(expected)
            raw = raw_path.read_bytes()
            if len(raw) != expected["size_bytes"] or _sha_bytes(raw) != expected["sha256"]:
                raise NativeWorkspaceInquiryError("recorded raw source binding differs")
        else:
            raise NativeWorkspaceInquiryError("source authority is outside the recorded adapter")
        if expected["media_type"] == "application/pdf" and not raw.startswith(b"%PDF-"):
            raise NativeWorkspaceInquiryError("recorded PDF magic differs")
        if expected["media_type"] == "image/jpeg" and not raw.startswith(b"\xff\xd8\xff"):
            raise NativeWorkspaceInquiryError("recorded JPEG magic differs")
        rendered = source.get("rendered")
        rendered_path = None
        if rendered is not None:
            rendered_path = raw_path if rendered.get("same_as_raw") else self.file_path(rendered)
            image = rendered_path.read_bytes()
            if len(image) != rendered["size_bytes"] or _sha_bytes(image) != rendered["sha256"]:
                raise NativeWorkspaceInquiryError("recorded native image binding differs")
        return {
            "source_key": source_key,
            "source_ids": deepcopy(source["source_ids"]),
            "observed_at": source["observed_at"],
            "raw_path": str(raw_path),
            "raw_sha256": expected["sha256"],
            "raw_size_bytes": expected["size_bytes"],
            "media_type": expected["media_type"],
            "rendered_path": str(rendered_path) if rendered_path else None,
            "rendered_sha256": rendered.get("sha256") if rendered else None,
        }

    def verify_sources(self, source_keys: list[str]) -> list[dict[str, Any]]:
        if len(source_keys) != len(set(source_keys)):
            raise NativeWorkspaceInquiryError("admitted source roster has duplicates")
        receipts = [self._verify_source(key) for key in source_keys]
        observed = [_aware(row["observed_at"], "source observed_at") for row in receipts]
        if observed != sorted(observed):
            raise NativeWorkspaceInquiryError("admitted sources are not in observation order")
        return receipts

    @staticmethod
    def _source_document(messages: list[dict[str, Any]], *, block_index: int = 0) -> dict[str, Any]:
        try:
            block = messages[1]["content"][block_index]
            if block["type"] != "text":
                raise KeyError
            value = json.loads(block["text"])
        except (IndexError, KeyError, TypeError, json.JSONDecodeError) as exc:
            raise NativeWorkspaceInquiryError("native input lacks its exact source document") from exc
        if not isinstance(value, dict):
            raise NativeWorkspaceInquiryError("native source document is invalid")
        return value

    def _rebind_messages(
        self, messages: list[dict[str, Any]], source_receipts: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        rebound = deepcopy(messages)
        rendered_by_source = {
            source_id: receipt
            for receipt in source_receipts
            if receipt["rendered_sha256"] is not None
            for source_id in receipt["source_ids"]
        }
        for block in rebound[1]["content"]:
            if block.get("type") != "image":
                continue
            image_id = block.get("image_id")
            document = self._source_document(rebound)
            matches = [row for row in document["image_views"] if row["ref"] == image_id]
            if len(matches) != 1:
                raise NativeWorkspaceInquiryError("native image alias does not resolve exactly once")
            receipt = rendered_by_source.get(matches[0]["source_id"])
            if receipt is None or block.get("sha256") != receipt["rendered_sha256"]:
                raise NativeWorkspaceInquiryError("native image source binding differs")
            block["image_path"] = receipt["rendered_path"]
        return rebound

    def _verify_document(
        self,
        document: Mapping[str, Any],
        *,
        source_receipts: list[dict[str, Any]],
        previous: Mapping[str, Any] | None,
        observed_at: str,
    ) -> None:
        if document.get("observed_at") != observed_at:
            raise NativeWorkspaceInquiryError("native observation clock differs")
        expected_prior = [] if previous is None else _model_prior(previous)
        if document.get("prior_self") != expected_prior:
            raise NativeWorkspaceInquiryError("native own prior differs")
        allowed_ids = {
            source_id for receipt in source_receipts for source_id in receipt["source_ids"]
        }
        visible_ids = {
            row.get("source_id") for field in ("text_views", "image_views")
            for row in document.get(field, []) if isinstance(row, dict)
        }
        if visible_ids != allowed_ids:
            raise NativeWorkspaceInquiryError("native source prefix differs from admitted sources")
        if any(
            _aware(row["first_observed_at"], "view first_observed_at")
            > _aware(observed_at, "observed_at")
            for field in ("text_views", "image_views")
            for row in document.get(field, [])
        ):
            raise NativeWorkspaceInquiryError("native input contains a future source")
        # The message projections must be exact partitions of the admitted raw
        # PublicCorpus message, not an authored fixture summary.
        message = next(row for row in source_receipts if row["source_key"] == "original_message")
        raw = Path(message["raw_path"]).read_text(encoding="utf-8")
        headers, body = raw.split("\n\n", 1)
        projected = {
            row["view_id"]: "".join(unit["text"] for unit in row["units"])
            for row in document["text_views"] if row["source_id"] == "source_001"
        }
        if projected != {
            "message.body.text_plain.001": body,
            "message.headers.raw.001": headers,
        }:
            raise NativeWorkspaceInquiryError("public message projections differ from raw bytes")

    def replay_native(
        self,
        call_id: str,
        *,
        source_keys: list[str],
        previous: Mapping[str, Any] | None,
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        call = self.calls[call_id]
        if (
            call.get("kind") != "native_reader"
            or tuple(call.get("source_keys", ())) != tuple(source_keys)
        ):
            raise NativeWorkspaceInquiryError("native call does not match the selected trace")
        sources = self.verify_sources(source_keys)
        messages = _load(self.file_path(call["input"]))["messages"]
        if _sha_bytes(_canonical(messages)) != call["messages_sha256"]:
            raise NativeWorkspaceInquiryError("recorded native messages identity differs")
        document = self._source_document(messages)
        self._verify_document(
            document,
            source_receipts=sources,
            previous=previous,
            observed_at=call["observed_at"],
        )
        rebound = self._rebind_messages(messages, sources)
        if _message_identity(messages) != _message_identity(rebound):
            raise NativeWorkspaceInquiryError("native path rebinding changed model-visible input")
        output = _load(self.file_path(call["output"]))
        _model_prior(output)
        receipt = {
            "call_id": call_id,
            "kind": call["kind"],
            "observed_at": call["observed_at"],
            "recorded_input_sha256": call["input"]["sha256"],
            "recorded_messages_sha256": call["messages_sha256"],
            "rebound_messages_sha256": _sha_bytes(_canonical(rebound)),
            "model_visible_messages_sha256": _message_identity(rebound),
            "image_sha256_order": [
                block["sha256"] for block in rebound[1]["content"]
                if block.get("type") == "image"
            ],
            "previous_output_sha256": None if previous is None else _sha_bytes(_canonical(previous)),
            "output_sha256": call["output"]["sha256"],
            "source_receipts": sources,
            "fresh_inference": False,
        }
        return output, receipt, document

    def replay_refinement(
        self,
        *,
        source_keys: list[str],
        previous: Mapping[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        call = self.calls["generic_refinement"]
        if (
            call.get("kind") != "generic_self_refinement"
            or tuple(call.get("source_keys", ())) != tuple(source_keys)
        ):
            raise NativeWorkspaceInquiryError("refinement call does not match the selected trace")
        sources = self.verify_sources(source_keys)
        source_messages = _load(self.file_path(call["source_input"]))["messages"]
        document = self._source_document(source_messages)
        self._verify_document(
            document, source_receipts=sources, previous=None, observed_at=call["observed_at"]
        )
        if _sha_bytes(_canonical(previous)) != call["previous_output_canonical_sha256"]:
            raise NativeWorkspaceInquiryError("refinement prior differs")
        text_parts = [
            block["text"] for block in source_messages[1]["content"]
            if block.get("type") == "text"
        ]
        constructed = (
            "\n\n".join(text_parts)
            + "\n\nGENERIC SELF-REFINEMENT INSTRUCTION:\n"
            + self.file_path(call["instruction"]).read_text(encoding="utf-8").rstrip("\n")
            + "\n\nFALLIBLE CANDIDATE JSON (NOT EVIDENCE):\n"
            + self.file_path(self.calls["initial_read"]["output"]).read_text(encoding="utf-8")
        )
        if constructed.encode("utf-8") != self.file_path(call["stdin"]).read_bytes():
            raise NativeWorkspaceInquiryError("generic refinement input differs")
        rebound = self._rebind_messages(source_messages, sources)
        if _message_identity(source_messages) != _message_identity(rebound):
            raise NativeWorkspaceInquiryError("refinement path rebinding changed model-visible input")
        output = _load(self.file_path(call["output"]))
        _model_prior(output)
        receipt = {
            "call_id": "generic_refinement",
            "kind": call["kind"],
            "observed_at": call["observed_at"],
            "stdin_sha256": call["stdin"]["sha256"],
            "system_sha256": _sha_bytes(source_messages[0]["content"].encode("utf-8")),
            "recorded_source_messages_sha256": _sha_bytes(_canonical(source_messages)),
            "rebound_source_messages_sha256": _sha_bytes(_canonical(rebound)),
            "model_visible_source_messages_sha256": _message_identity(rebound),
            "image_sha256_order": [
                block["sha256"] for block in source_messages[1]["content"]
                if block.get("type") == "image"
            ],
            "previous_output_sha256": call["previous_output_canonical_sha256"],
            "output_sha256": call["output"]["sha256"],
            "source_receipts": sources,
            "fresh_inference": False,
        }
        return output, receipt

    def replay_correction_target(
        self,
        *,
        source_keys: list[str],
        previous: Mapping[str, Any],
        opaque_registry: list[dict[str, Any]],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        call = self.calls["correction_target"]
        sources = self.verify_sources(source_keys)
        messages = _load(self.file_path(call["input"]))["messages"]
        task = json.loads(messages[1]["content"][0]["text"])
        document = self._source_document(messages, block_index=1)
        self._verify_document(
            document, source_receipts=sources, previous=previous, observed_at=call["observed_at"]
        )
        if task.get("prior_assertion_registry") != opaque_registry:
            raise NativeWorkspaceInquiryError("correction target registry differs from admitted prior sources")
        rebound = deepcopy(messages)
        # Target call has one task block before the continuation document.
        native_tail = [{"role": messages[0]["role"], "content": messages[0]["content"]}, {
            "role": messages[1]["role"], "content": messages[1]["content"][1:]
        }]
        rebound_tail = self._rebind_messages(native_tail, sources)
        rebound[1]["content"][1:] = rebound_tail[1]["content"]
        if _message_identity(messages) != _message_identity(rebound):
            raise NativeWorkspaceInquiryError("correction target path rebinding changed model-visible input")
        output = _load(self.file_path(call["output"]))
        if set(output) != {"ambiguities", "corrections"} or output["ambiguities"] != []:
            raise NativeWorkspaceInquiryError("correction target output differs from its contract")
        receipt = {
            "call_id": "correction_target",
            "kind": call["kind"],
            "observed_at": call["observed_at"],
            "recorded_input_sha256": call["input"]["sha256"],
            "recorded_messages_sha256": call["messages_sha256"],
            "rebound_messages_sha256": _sha_bytes(_canonical(rebound)),
            "model_visible_messages_sha256": _message_identity(rebound),
            "image_sha256_order": [
                block["sha256"] for block in rebound[1]["content"]
                if block.get("type") == "image"
            ],
            "output_sha256": call["output"]["sha256"],
            "source_receipts": sources,
            "fresh_inference": False,
        }
        return output, receipt


class NativeWorkspaceInquiryServiceV1:
    """Persisted workspace entry around the recorded provider and inquiry journal."""

    INITIAL_KEYS = ("original_message", "original_image", "initial_report")
    RESPONSE_KEYS = (*INITIAL_KEYS, "requested_response")
    CORRECTION_KEYS = (*RESPONSE_KEYS, "unrelated_correction")

    def __init__(self, *, corpus: PublicCorpus, database: Path, trace_manifest: Path) -> None:
        self.corpus = corpus
        self.database = database
        self.provider = RecordedNativeProviderV1(trace_manifest, corpus)
        binding = corpus.binding(EXPECTED_CLAIM_ID)
        declared = self.provider.manifest["claim_binding"]
        if (
            binding["binding_sha256"] != declared["binding_sha256"]
            or binding["claim"]["sha256"] != declared["claim_sha256"]
            or corpus.source_registry(EXPECTED_CLAIM_ID).get("case_id") != EXPECTED_CLAIM_ID
            or _sha_bytes(_canonical(corpus.source_registry(EXPECTED_CLAIM_ID)))
            != declared["source_registry_canonical_sha256"]
        ):
            raise NativeWorkspaceInquiryError("workspace claim binding differs from recorded trace")

    def _journal(self) -> InquiryJournal:
        self.database.parent.mkdir(parents=True, exist_ok=True)
        return InquiryJournal(self.database)

    def _service(self, journal: InquiryJournal) -> InquiryService:
        return InquiryService(
            journal, capabilities=CAPABILITIES, source_adapter_id=NATIVE_SOURCE_ADAPTER_ID
        )

    @staticmethod
    def _stream_id(claim_id: str) -> str:
        return "native-workspace-inquiry." + digest_value({
            "contract": NATIVE_ENTRY_CONTRACT, "claim_id": claim_id,
            "trajectory": "metered-frontier-refinement-r1+frontier-correction-target-r1",
        })

    def _require_claim(self, claim_id: str) -> None:
        if claim_id != EXPECTED_CLAIM_ID:
            raise NativeWorkspaceInquiryError("claim is outside the recorded development trace")
        self.corpus.binding(claim_id)

    @staticmethod
    def _events_by_type(events: list[dict[str, Any]], event_type: str) -> list[dict[str, Any]]:
        return [event for event in events if event["event_type"] == event_type]

    @staticmethod
    def _append_custom(
        journal: InquiryJournal,
        *,
        stream_id: str,
        idempotency_key: str,
        event_type: str,
        payload: Mapping[str, Any],
    ) -> dict[str, Any]:
        events = journal.events(stream_id)
        return journal.append(
            stream_id=stream_id,
            idempotency_key=idempotency_key,
            event_type=event_type,
            payload=payload,
            expected_parent_sha256=events[-1]["event_sha256"] if events else None,
            check_parent=True,
        )

    def _artifact_binding(
        self, receipt: Mapping[str, Any], input_path: Path, source_prefix_sha256: str
    ) -> dict[str, Any]:
        return {
            "raw_artifact_sha256": receipt["raw_sha256"],
            "raw_artifact_path": receipt["raw_path"],
            "rendered_image_sha256": receipt["rendered_sha256"],
            "rendered_image_path": receipt["rendered_path"],
            "input_receipt_sha256": _sha(input_path),
            "input_receipt_path": str(input_path),
            "artifact_registry_sha256": _sha(self.provider.manifest_path),
            "artifact_registry_path": str(self.provider.manifest_path),
            "source_prefix_sha256": source_prefix_sha256,
            "binding_status": "HASH_VERIFIED_LOCAL_REPLAY",
        }

    def _assertions(
        self,
        document: Mapping[str, Any],
        source_receipts: list[dict[str, Any]],
        *,
        refs: set[str] | None = None,
        input_path: Path,
    ) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
        receipt_by_source = {
            source_id: receipt
            for receipt in source_receipts for source_id in receipt["source_ids"]
            if any(view["source_id"] == source_id for view in document["text_views"])
        }
        prefix_sha = digest_value({
            "text_views": document["text_views"], "image_views": document["image_views"]
        })
        assertions, by_ref = [], {}
        for view in document["text_views"]:
            receipt = receipt_by_source[view["source_id"]]
            binding = self._artifact_binding(receipt, input_path, prefix_sha)
            for unit in view["units"]:
                if refs is not None and unit["ref"] not in refs:
                    continue
                assertion = source_assertion_from_view(
                    view,
                    ref=unit["ref"],
                    adapter_id=NATIVE_SOURCE_ADAPTER_ID,
                    proposed_role="source_reported",
                    artifact_binding=binding,
                )
                assertions.append(assertion)
                by_ref[unit["ref"]] = assertion
        return assertions, by_ref

    def _grouped_assertion(
        self,
        document: Mapping[str, Any],
        source_receipts: list[dict[str, Any]],
        *,
        refs: list[str],
        input_path: Path,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Bind the model-selected refs to one exact contiguous source span."""

        if not refs or len(refs) != len(set(refs)):
            raise NativeWorkspaceInquiryError("model correction refs are empty or duplicated")
        locations: list[tuple[dict[str, Any], int]] = []
        for view in document["text_views"]:
            for index, unit in enumerate(view["units"]):
                if unit["ref"] in refs:
                    locations.append((view, index))
        if len(locations) != len(refs):
            raise NativeWorkspaceInquiryError("not every model correction ref resolves exactly once")
        keys = {(view["source_id"], view["view_id"]) for view, _ in locations}
        if len(keys) != 1:
            raise NativeWorkspaceInquiryError("model correction refs cross source-view boundaries")
        view = locations[0][0]
        indexes = [index for _, index in locations]
        first, last = min(indexes), max(indexes)
        full_text = "".join(unit["text"] for unit in view["units"])
        offsets, cursor = [], 0
        for unit in view["units"]:
            offsets.append(cursor)
            cursor += len(unit["text"])
        start = offsets[first]
        end = offsets[last] + len(view["units"][last]["text"])
        span = full_text[start:end]
        included = [unit["ref"] for unit in view["units"][first:last + 1]]
        receipt = next(
            row for row in source_receipts if view["source_id"] in row["source_ids"]
        )
        prefix_sha = digest_value({
            "text_views": document["text_views"], "image_views": document["image_views"]
        })
        binding = self._artifact_binding(receipt, input_path, prefix_sha)
        source_ref = ClaimSourceRef.model_validate({
            "source_id": view["source_id"],
            "source_sha256": digest_text(full_text),
            "source_version": f"{view['view_id']}@{view['first_observed_at']}",
            "locator_kind": "text_quote",
            # This recorded trajectory contains only first-page/message views.
            "page": 1,
            "sanitized_excerpt": span,
            "text_start": start,
            "text_end": end,
            "field": None,
            "value": None,
            "span_sha256": digest_text(span),
            "adapter_id": NATIVE_SOURCE_ADAPTER_ID,
        })
        material = {
            "contract": "casepath.provisional-source-assertion/1.0.0",
            "source_ref": source_ref.model_dump(mode="json"),
            "reported_text": span,
            "proposed_role": "source_reported",
            "role_status": "PROPOSED_UNVERIFIED",
            "truth_status": "SOURCE_REPORTED_NOT_WORLD_VERIFIED",
            "identity_scope": "DERIVED_RENDERED_TEXT_VIEW",
            "original_artifact_binding": binding,
        }
        identity = digest_value(material)
        assertion = validate_source_assertion({
            **material,
            "assertion_id": "assertion." + identity,
            "assertion_sha256": identity,
            "status": "active",
        })
        return assertion, {
            "strategy": "SAME_VIEW_MIN_MAX_CONTIGUOUS_OFFSETS",
            "source_id": view["source_id"],
            "view_id": view["view_id"],
            "requested_refs": refs,
            "included_refs": included,
            "intervening_refs": [ref for ref in included if ref not in set(refs)],
            "char_start": start,
            "char_end": end,
            "span_sha256": digest_text(span),
            "preserves_intervening_bytes": True,
        }

    @staticmethod
    def _opaque_registry(
        document: Mapping[str, Any], prior_assertions: Mapping[str, Mapping[str, Any]]
    ) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
        rows, mapping = [], {}
        for view in document["text_views"]:
            for unit in view["units"]:
                if unit["ref"] not in prior_assertions:
                    continue
                identity = {
                    "source_id": view["source_id"], "view_id": view["view_id"],
                    "ref": unit["ref"], "text": unit["text"],
                }
                opaque = "a_" + _sha_bytes(_canonical(identity))[:20]
                row = {
                    "assertion_id": opaque,
                    "label": "source_reported",
                    "source_id": view["source_id"],
                    "view_id": view["view_id"],
                    "source_ref": unit["ref"],
                    "text": unit["text"],
                }
                rows.append(row)
                mapping[opaque] = {
                    "row": row,
                    "canonical_assertion": deepcopy(prior_assertions[unit["ref"]]),
                }
        return rows, mapping

    @staticmethod
    def _suggested_actions(output: Mapping[str, Any]) -> list[dict[str, Any]]:
        result = []
        internal_markers = ("prüfung", "schutzschritte", "aufstellung")
        for row in _model_prior(output):
            if row["state"] in {"received", "withdrawn", "conditional"}:
                continue
            description = row["description"]
            channel = (
                "internal_review"
                if any(marker in description.casefold() for marker in internal_markers)
                else "external_evidence_request"
            )
            result.append({
                "need_id": row["need_id"],
                "description": description,
                "model_state": row["state"],
                "suggested_channel": channel,
                "authority": "FALLIBLE_DISPLAY_HEURISTIC_OVER_MODEL_TEXT",
                "router_id": "casepath.recorded-entry-display-channel-heuristic/1.0.0",
            })
        return result

    def open(self, claim_id: str, *, idempotency_key: str) -> dict[str, Any]:
        self._require_claim(claim_id)
        stream_id = self._stream_id(claim_id)
        journal = self._journal()
        try:
            existing = journal.events(stream_id)
            opened = self._events_by_type(existing, "NATIVE_INITIAL_REPLAY_RECORDED")
            if opened and opened[0]["idempotency_key"] != idempotency_key + ".provider":
                raise NativeWorkspaceInquiryConflict("native workspace entry is already open")
            initial, initial_receipt, document = self.provider.replay_native(
                "initial_read", source_keys=self.INITIAL_KEYS, previous=None
            )
            refined, refinement_receipt = self.provider.replay_refinement(
                source_keys=self.INITIAL_KEYS, previous=initial
            )
            sources = self.provider.verify_sources(self.INITIAL_KEYS)
            initial_input = self.provider.file_path(
                self.provider.calls["initial_read"]["input"]
            )
            assertions, _ = self._assertions(
                document, sources, input_path=initial_input
            )
            service = self._service(journal)
            service.register_source_assertions(
                stream_id=stream_id,
                assertions=assertions,
                observed_at=document["observed_at"],
                idempotency_key=idempotency_key + ".sources",
            )
            self._append_custom(
                journal,
                stream_id=stream_id,
                idempotency_key=idempotency_key + ".provider",
                event_type="NATIVE_INITIAL_REPLAY_RECORDED",
                payload={
                    "observed_at": document["observed_at"],
                    "initial_call": initial_receipt,
                    "refinement_call": refinement_receipt,
                    "initial_output_sha256": _sha_bytes(_canonical(initial)),
                    "output": refined,
                    "output_sha256": _sha_bytes(_canonical(refined)),
                    "selected_trajectory": self.provider.manifest["selected_trajectory"],
                    "canonical_fact_effect": None,
                    "readiness_effect": None,
                },
            )
            policy_path = self.provider.file_path(
                self.provider.manifest["trajectory_policy"]
            )
            policy = _load(policy_path)
            packet = policy["step1"]["selected_request_packet"]
            candidates = [row for row in refined["needs"] if row["description"] == packet["description"]]
            if len(candidates) != 1:
                raise NativeWorkspaceInquiryError("recorded request no longer selects one model proposal")
            candidate = candidates[0]
            event = service.admit_inquiry(
                stream_id=stream_id,
                reader_proposal={
                    "description": candidate["description"],
                    "warrants": packet["all_warrants"],
                    "warrant_artifact_bindings": {
                        "source_001::message.body.text_plain.001": self._artifact_binding(
                            next(row for row in sources if row["source_key"] == "original_message"),
                            initial_input,
                            policy["step1"]["initial_prefix_sha256"],
                        )
                    },
                    "reader_output_sha256": _sha_bytes(_canonical(refined)),
                    "reader_proposal_sha256": digest_value(candidate),
                },
                channel_proposal={
                    "channel": "external_evidence_request",
                    "proposed_by": "selected_recorded_trajectory_policy",
                    "proposal_source_sha256": _sha(policy_path),
                    "semantic_authority": "fallible_proposal_only",
                },
                observed_at=document["observed_at"],
                idempotency_key=idempotency_key + ".inquiry",
            )
            self._append_custom(
                journal,
                stream_id=stream_id,
                idempotency_key=idempotency_key + ".draft",
                event_type="NATIVE_REQUEST_DRAFT_RECORDED",
                payload={
                    "observed_at": document["observed_at"],
                    "inquiry_id": event["payload"]["inquiry_id"],
                    "need_id": candidate["need_id"],
                    "request_packet": packet,
                    "trajectory_policy_sha256": _sha(policy_path),
                    "authority": "PROVISIONAL_RECORDED_RESEARCH_DRAFT",
                },
            )
            return self._state(journal, claim_id, replayed=bool(opened))
        except InquiryError as exc:
            raise NativeWorkspaceInquiryError(str(exc)) from exc
        finally:
            journal.close()

    def dispatch(
        self,
        claim_id: str,
        *,
        expected_state_sha256: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        self._require_claim(claim_id)
        stream_id = self._stream_id(claim_id)
        journal = self._journal()
        try:
            events = journal.events(stream_id)
            drafts = self._events_by_type(events, "NATIVE_REQUEST_DRAFT_RECORDED")
            if len(drafts) != 1:
                raise NativeWorkspaceInquiryConflict("recorded request draft is unavailable")
            issued = self._events_by_type(events, "REQUEST_ISSUED")
            if issued:
                if issued[0]["idempotency_key"] != idempotency_key:
                    raise NativeWorkspaceInquiryConflict("recorded request is already dispatched")
                return self._state(journal, claim_id, replayed=True)
            if self._state(journal, claim_id, replayed=False)["state_sha256"] != expected_state_sha256:
                raise NativeWorkspaceInquiryConflict("native inquiry state changed before dispatch")
            draft = drafts[0]["payload"]
            event = self._service(journal).issue_request(
                stream_id=stream_id,
                inquiry_id=draft["inquiry_id"],
                request_packet=draft["request_packet"],
                recorded_dispatch_provenance={
                    "kind": "recorded_research_dispatch",
                    "trajectory_policy_sha256": draft["trajectory_policy_sha256"],
                    "not_an_external_delivery_receipt": True,
                },
                issued_at=draft["observed_at"],
                idempotency_key=idempotency_key,
            )
            return self._state(
                journal, claim_id, replayed=event.get("replayed", False)
            )
        except InquiryError as exc:
            raise NativeWorkspaceInquiryError(str(exc)) from exc
        finally:
            journal.close()

    def admit_recorded_response(
        self,
        claim_id: str,
        *,
        request_id: str,
        expected_state_sha256: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        self._require_claim(claim_id)
        stream_id = self._stream_id(claim_id)
        journal = self._journal()
        try:
            before = self._state(journal, claim_id, replayed=False)
            existing = self._events_by_type(journal.events(stream_id), "RESPONSE_RECORDED")
            if existing:
                if (
                    existing[0]["idempotency_key"] != idempotency_key + ".response"
                    or existing[0]["payload"]["request_id"] != request_id
                ):
                    raise NativeWorkspaceInquiryConflict("recorded response is already admitted")
                provider_events = [
                    event for event in self._events_by_type(
                        journal.events(stream_id), "NATIVE_UPDATE_REPLAY_RECORDED"
                    ) if event["payload"].get("phase") == "after_response"
                ]
                if provider_events:
                    if provider_events[0]["idempotency_key"] != idempotency_key + ".provider":
                        raise NativeWorkspaceInquiryConflict("response provider replay already has another identity")
                    return self._state(journal, claim_id, replayed=True)
            elif before["state_sha256"] != expected_state_sha256:
                raise NativeWorkspaceInquiryConflict("native inquiry state changed before response admission")
            inquiry_state = self._service(journal).state(stream_id)
            request = inquiry_state["requests"].get(request_id)
            if request is None:
                raise NativeWorkspaceInquiryError("response does not match the issued request")
            initial_events = self._events_by_type(
                journal.events(stream_id), "NATIVE_INITIAL_REPLAY_RECORDED"
            )
            if len(initial_events) != 1:
                raise NativeWorkspaceInquiryConflict("initial reader prior is unavailable")
            prior = initial_events[0]["payload"]["output"]
            output, call_receipt, document = self.provider.replay_native(
                "after_response", source_keys=self.RESPONSE_KEYS, previous=prior
            )
            sources = self.provider.verify_sources(self.RESPONSE_KEYS)
            assertions, _ = self._assertions(
                document,
                sources,
                refs={f"t{number}" for number in range(31, 49)},
                input_path=self.provider.file_path(
                    self.provider.calls["after_response"]["input"]
                ),
            )
            if not existing:
                self._service(journal).record_response(
                    stream_id=stream_id,
                    inquiry_id=request["inquiry_id"],
                    request_id=request_id,
                    source_assertions=assertions,
                    recorded_arrival_provenance={
                        "kind": "recorded_research_arrival",
                        "source_receipt": next(
                            row for row in call_receipt["source_receipts"]
                            if row["source_key"] == "requested_response"
                        ),
                        "not_a_live_external_response_receipt": True,
                    },
                    reader_update_sha256=call_receipt["output_sha256"],
                    observed_at=document["observed_at"],
                    idempotency_key=idempotency_key + ".response",
                )
            self._append_custom(
                journal,
                stream_id=stream_id,
                idempotency_key=idempotency_key + ".provider",
                event_type="NATIVE_UPDATE_REPLAY_RECORDED",
                payload={
                    "phase": "after_response",
                    "observed_at": document["observed_at"],
                    "call": call_receipt,
                    "output": output,
                    "output_sha256": _sha_bytes(_canonical(output)),
                    "canonical_fact_effect": None,
                    "readiness_effect": None,
                },
            )
            return self._state(journal, claim_id, replayed=bool(existing))
        except InquiryError as exc:
            raise NativeWorkspaceInquiryError(str(exc)) from exc
        finally:
            journal.close()

    def admit_recorded_correction(
        self,
        claim_id: str,
        *,
        expected_state_sha256: str,
        expected_opaque_target_id: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        self._require_claim(claim_id)
        stream_id = self._stream_id(claim_id)
        journal = self._journal()
        try:
            before = self._state(journal, claim_id, replayed=False)
            existing = self._events_by_type(journal.events(stream_id), "SOURCE_ASSERTION_CORRECTED")
            if existing:
                recorded_target = existing[0]["payload"]["recorded_arrival_provenance"][
                    "supersession"
                ]["prior_assertion_id"]
                if (
                    existing[0]["idempotency_key"] != idempotency_key + ".correction"
                    or recorded_target != expected_opaque_target_id
                ):
                    raise NativeWorkspaceInquiryConflict("recorded correction is already applied")
                provider_events = [
                    event for event in self._events_by_type(
                        journal.events(stream_id), "NATIVE_UPDATE_REPLAY_RECORDED"
                    ) if event["payload"].get("phase") == "after_correction"
                ]
                if provider_events:
                    if provider_events[0]["idempotency_key"] != idempotency_key + ".provider":
                        raise NativeWorkspaceInquiryConflict("correction provider replay already has another identity")
                    return self._state(journal, claim_id, replayed=True)
            elif before["state_sha256"] != expected_state_sha256:
                raise NativeWorkspaceInquiryConflict("native inquiry state changed before correction")
            response_updates = [
                event for event in self._events_by_type(
                    journal.events(stream_id), "NATIVE_UPDATE_REPLAY_RECORDED"
                ) if event["payload"].get("phase") == "after_response"
            ]
            if len(response_updates) != 1:
                raise NativeWorkspaceInquiryConflict("response reader prior is unavailable")
            previous = response_updates[0]["payload"]["output"]
            actor_output, actor_receipt, document = self.provider.replay_native(
                "after_correction", source_keys=self.CORRECTION_KEYS, previous=previous
            )
            sources = self.provider.verify_sources(self.CORRECTION_KEYS)
            inquiry_state = self._service(journal).state(stream_id)
            # Recreate the literal t0..t48 opaque registry from the exact
            # current source rows and their canonical provisional assertions.
            prior_document = self.provider._source_document(
                _load(self.provider.file_path(
                    self.provider.calls["after_response"]["input"]
                ))["messages"]
            )
            state_by_ref: dict[str, dict[str, Any]] = {}
            for assertion in inquiry_state["source_assertions"].values():
                ref_text = assertion["reported_text"]
                matches = [
                    unit["ref"] for view in prior_document["text_views"] for unit in view["units"]
                    if unit["text"] == ref_text
                    and view["source_id"] == assertion["source_ref"]["source_id"]
                ]
                for ref in matches:
                    state_by_ref.setdefault(ref, assertion)
            opaque_registry, opaque_map = self._opaque_registry(prior_document, state_by_ref)
            target_output, target_receipt = self.provider.replay_correction_target(
                source_keys=self.CORRECTION_KEYS,
                previous=previous,
                opaque_registry=opaque_registry,
            )
            supersessions = [
                row for row in target_output["corrections"] if row.get("relation") == "supersedes"
            ]
            confirmations = [
                row for row in target_output["corrections"] if row.get("relation") == "confirms_unchanged"
            ]
            if len(supersessions) != 1 or len(confirmations) != 1:
                raise NativeWorkspaceInquiryError("recorded correction relation roster differs")
            superseding = supersessions[0]
            confirmation = confirmations[0]
            if superseding["prior_assertion_id"] != expected_opaque_target_id:
                raise NativeWorkspaceInquiryConflict("client correction target differs from model proposal")
            target = opaque_map.get(superseding["prior_assertion_id"])
            confirmed = opaque_map.get(confirmation["prior_assertion_id"])
            if (
                target is None
                or confirmed is None
                or target["row"]["source_ref"] != superseding["prior_source_ref"]
                or confirmed["row"]["source_ref"] != confirmation["prior_source_ref"]
            ):
                raise NativeWorkspaceInquiryError("model correction target is not bound to prior source bytes")
            allowed_new = {
                unit["ref"] for view in document["text_views"]
                if view["source_id"] == "research_source_18262005cacae2"
                for unit in view["units"]
            }
            if any(
                not refs or any(ref not in allowed_new for ref in refs)
                for refs in (superseding["new_source_refs"], confirmation["new_source_refs"])
            ):
                raise NativeWorkspaceInquiryError("model correction cites outside the new source")
            selected_refs = list(dict.fromkeys(
                ref for relation in target_output["corrections"]
                for ref in relation["new_source_refs"]
            ))
            grouped_assertion, grouping = self._grouped_assertion(
                document,
                sources,
                refs=selected_refs,
                input_path=self.provider.file_path(
                    self.provider.calls["after_correction"]["input"]
                ),
            )
            if not existing:
                self._service(journal).apply_source_correction(
                    stream_id=stream_id,
                    target_assertion_id=target["canonical_assertion"]["assertion_id"],
                    correction_assertion=grouped_assertion,
                    neighbor_assertions=[],
                    recorded_arrival_provenance={
                        "kind": "recorded_model_targeted_source_correction",
                        "source_receipt": next(
                            row for row in actor_receipt["source_receipts"]
                            if row["source_key"] == "unrelated_correction"
                        ),
                        "model_output_sha256": target_receipt["output_sha256"],
                        "supersession": superseding,
                        "confirmation": confirmation,
                        "grouping": grouping,
                        "not_a_canonical_correction_receipt": True,
                    },
                    observed_at=document["observed_at"],
                    idempotency_key=idempotency_key + ".correction",
                )
            self._append_custom(
                journal,
                stream_id=stream_id,
                idempotency_key=idempotency_key + ".provider",
                event_type="NATIVE_UPDATE_REPLAY_RECORDED",
                payload={
                    "phase": "after_correction",
                    "observed_at": document["observed_at"],
                    "call": actor_receipt,
                    "output": actor_output,
                    "output_sha256": _sha_bytes(_canonical(actor_output)),
                    "correction_target_call": target_receipt,
                    "correction_target_output": target_output,
                    "grouping": grouping,
                    "canonical_fact_effect": None,
                    "readiness_effect": None,
                },
            )
            return self._state(journal, claim_id, replayed=bool(existing))
        except InquiryError as exc:
            raise NativeWorkspaceInquiryError(str(exc)) from exc
        finally:
            journal.close()

    def state(self, claim_id: str) -> dict[str, Any]:
        self._require_claim(claim_id)
        journal = self._journal()
        try:
            return self._state(journal, claim_id, replayed=False)
        finally:
            journal.close()

    def _state(
        self, journal: InquiryJournal, claim_id: str, *, replayed: bool
    ) -> dict[str, Any]:
        stream_id = self._stream_id(claim_id)
        events = journal.events(stream_id)
        service_state = self._service(journal).state(stream_id)
        initial = self._events_by_type(events, "NATIVE_INITIAL_REPLAY_RECORDED")
        updates = self._events_by_type(events, "NATIVE_UPDATE_REPLAY_RECORDED")
        proposal = updates[-1]["payload"]["output"] if updates else (
            initial[-1]["payload"]["output"] if initial else None
        )
        issued = self._events_by_type(events, "REQUEST_ISSUED")
        responses = self._events_by_type(events, "RESPONSE_RECORDED")
        corrections = self._events_by_type(events, "SOURCE_ASSERTION_CORRECTED")
        if corrections:
            stage = "correction_applied"
        elif responses:
            stage = "response_observed"
        elif issued:
            stage = "request_recorded"
        elif initial:
            stage = "draft_ready"
        else:
            stage = "not_started"
        request = deepcopy(issued[0]["payload"]) if issued else None
        material = {
            "contract": NATIVE_ENTRY_CONTRACT,
            "research_mode": NATIVE_RESEARCH_MODE,
            "claim_id": claim_id,
            "stream_id": stream_id,
            "stage": stage,
            "revision": len(events),
            "last_event_sha256": events[-1]["event_sha256"] if events else None,
            "selected_trajectory": self.provider.manifest["selected_trajectory"],
            "latest_model_proposal": deepcopy(proposal),
            "suggested_actions": [] if proposal is None else self._suggested_actions(proposal),
            "recorded_request": request,
            "response_count": len(responses),
            "correction_count": len(corrections),
            "provider_call_receipts": [
                row
                for event in [*initial, *updates]
                for key in ("initial_call", "refinement_call", "call", "correction_target_call")
                if (row := event["payload"].get(key)) is not None
            ],
            "provisional_source_assertions": service_state["source_assertions"],
            "canonical_facts": {},
            "certified_readiness": None,
            "limits": [
                "Recorded replay validates transport, byte provenance and state transitions; it is not fresh model performance.",
                "Model needs, channels and correction relations are fallible proposals.",
                "No original-world truth, legal sufficiency or global readiness is certified.",
                "Recorded dispatch has no live external-delivery receipt.",
                "The selected trace uses first-page/message views; broader page binding is outside this adapter.",
            ],
        }
        return {
            **material,
            "state_sha256": digest_value(material),
            "replayed": replayed,
        }
