from __future__ import annotations

import base64
import binascii
import json
import os
import re
import stat
import tempfile
import unicodedata
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Callable, Literal

from pydantic import Field, StrictInt, model_validator

from .claim_loop import (
    ClaimLoopError,
    ToolResult,
    adapter_implementation_sha256_v1,
    playbook_template_from_accepted_v1,
)
from .claim_loop_contracts import (
    AcquisitionReceiptV1,
    CanonicalFactInterpretationV1,
    ClaimLoopState,
    ClaimObservation,
    ClaimSourceRef,
    EvidenceAction,
    ToolResultStatus,
)
from .foundation.common import canonical_json_bytes, digest_text, digest_value, is_sha256
from .foundation.contracts import FoundationModel
from .workspace_evidence_independent_authority_v1 import (
    IndependentWorkspaceEvidenceAuthorityV1,
)


LOOPBACK_SOURCE_BYTE_ADAPTER_ID = "loopback-source-byte-acquisition-v1"
EVIDENCE_REGISTRATION_SCHEMA = "casepath.workspace-evidence-registration/3.0.0"
EVIDENCE_REGISTRATION_FIELDS = (
    "schema",
    "action_id",
    "expected_revision",
    "idempotency_key",
    "acquisition_intent_id",
    "acquisition_receipt_id",
    "content_b64",
)
SOURCE_ACQUISITION_CHANNEL = "public-corpus-source-span-loopback-v1"
SOURCE_MEDIA_SNIFFER_ID = "casepath.strict-utf8-text-sniffer/1.0.0"
SOURCE_MEDIA_SNIFFER_SHA256 = digest_value(
    {
        "sniffer_id": SOURCE_MEDIA_SNIFFER_ID,
        "checks": ["nonempty", "max-100000", "strict-utf8", "unicode-nfc", "no-nul"],
        "result": "text/plain; charset=utf-8",
    }
)
INTERPRETATION_SCHEMA_ID = "casepath.workspace-source-span-interpretation/1.0.0"
INTERPRETATION_SCHEMA_SHA256 = digest_value(
    {
        "schema_id": INTERPRETATION_SCHEMA_ID,
        "input": "exact-receipted-source-span",
        "output": "canonical-fact-interpretation/1.2.0",
        "unknown_default": True,
    }
)
INTENT_TTL_SECONDS = 300
MAX_SOURCE_BYTES = 100_000


class WorkspaceEvidenceAuthorityError(ValueError):
    pass


def _module_sha256() -> str:
    return sha256(Path(__file__).read_bytes()).hexdigest()


def _parse_time(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise WorkspaceEvidenceAuthorityError("evidence authority timestamp is invalid") from exc
    if parsed.tzinfo is None:
        raise WorkspaceEvidenceAuthorityError("evidence authority timestamp lacks a timezone")
    return parsed.astimezone(timezone.utc)


def _now(value: str | None = None) -> tuple[str, datetime]:
    parsed = _parse_time(value) if value is not None else datetime.now(timezone.utc)
    return parsed.isoformat(), parsed


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _ensure_directory(path: Path) -> None:
    missing: list[Path] = []
    cursor = path
    while not cursor.exists():
        missing.append(cursor)
        if cursor.parent == cursor:
            raise WorkspaceEvidenceAuthorityError("evidence authority root is unavailable")
        cursor = cursor.parent
    if cursor.is_symlink() or not cursor.is_dir():
        raise WorkspaceEvidenceAuthorityError("evidence authority parent is invalid")
    for value in reversed(missing):
        value.mkdir()
        _fsync_directory(value.parent)
        _fsync_directory(value)


def _read_regular(path: Path) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink < 1:
            raise WorkspaceEvidenceAuthorityError("evidence authority resource is not regular")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 65_536)
            if not chunk:
                break
            chunks.append(chunk)
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def _publish_new(path: Path, payload: bytes) -> bool:
    _ensure_directory(path.parent)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb", closefd=True) as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, path)
            created = True
        except FileExistsError:
            created = False
        _fsync_directory(path.parent)
        return created
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
        _fsync_directory(path.parent)


def _resource_name(identity: str) -> str:
    return sha256(identity.encode("utf-8")).hexdigest() + ".json"


def decode_canonical_content_b64(value: str) -> bytes:
    if not isinstance(value, str) or not value or len(value) > (MAX_SOURCE_BYTES * 4 // 3 + 8):
        raise WorkspaceEvidenceAuthorityError("registered source base64 is empty or oversized")
    try:
        raw = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise WorkspaceEvidenceAuthorityError("registered source base64 is invalid") from exc
    if not raw or len(raw) > MAX_SOURCE_BYTES or base64.b64encode(raw).decode("ascii") != value:
        raise WorkspaceEvidenceAuthorityError("registered source base64 is not canonical")
    return raw


class WorkspaceAcquisitionIntentV1(FoundationModel):
    contract: Literal["casepath.workspace-acquisition-intent/1.0.0"] = (
        "casepath.workspace-acquisition-intent/1.0.0"
    )
    intent_id: str = Field(pattern=r"^intent\.[0-9a-f]{64}$")
    session_id: str
    loop_id: str
    claim_id: str
    record_version: str
    expected_revision: StrictInt = Field(ge=1)
    expected_state_sha256: str
    action_id: str
    action_sha256: str
    evidence_item_id: str
    idempotency_key: str = Field(min_length=8, max_length=128)
    adapter_id: Literal["loopback-source-byte-acquisition-v1"]
    claim_registry_watermark_sha256: str
    issued_at: str
    expires_at: str
    receipt_sha256: str

    @model_validator(mode="after")
    def validate_intent(self) -> "WorkspaceAcquisitionIntentV1":
        identity = self.model_dump(
            mode="json",
            exclude={"intent_id", "receipt_sha256", "issued_at", "expires_at"},
        )
        if (
            self.action_id != f"action.{self.action_sha256}"
            or not is_sha256(self.action_sha256)
            or not is_sha256(self.expected_state_sha256)
            or not is_sha256(self.claim_registry_watermark_sha256)
            or self.intent_id != "intent." + digest_value(identity)
            or _parse_time(self.expires_at) <= _parse_time(self.issued_at)
        ):
            raise ValueError("workspace acquisition intent identity is invalid")
        payload = self.model_dump(mode="json", exclude={"receipt_sha256"})
        if self.receipt_sha256 != digest_value(payload):
            raise ValueError("workspace acquisition intent self-hash differs")
        return self


class WorkspaceSourceAcquisitionReceiptV1(FoundationModel):
    contract: Literal["casepath.workspace-source-acquisition/1.0.0"] = (
        "casepath.workspace-source-acquisition/1.0.0"
    )
    acquisition_receipt_id: str = Field(pattern=r"^acquisition\.[0-9a-f]{64}$")
    acquisition_intent_id: str = Field(pattern=r"^intent\.[0-9a-f]{64}$")
    intent_receipt_sha256: str
    session_id: str
    loop_id: str
    claim_id: str
    record_version: str
    expected_revision: StrictInt = Field(ge=1)
    expected_state_sha256: str
    action_id: str
    action_sha256: str
    evidence_item_id: str
    idempotency_key: str = Field(min_length=8, max_length=128)
    adapter_id: Literal["loopback-source-byte-acquisition-v1"]
    adapter_artifact_sha256: str
    claim_registry_watermark_sha256: str
    claim_first_seen_receipt_sha256: str
    source_entry_sha256: str
    source_artifact_id: str
    source_artifact_sha256: str
    source_version: str
    text_start: StrictInt = Field(ge=0)
    text_end: StrictInt = Field(gt=0)
    byte_start: StrictInt = Field(ge=0)
    byte_end: StrictInt = Field(gt=0)
    content_sha256: str
    content_length: StrictInt = Field(ge=1, le=MAX_SOURCE_BYTES)
    server_sniffed_media_type: Literal["text/plain; charset=utf-8"]
    media_sniffer_id: Literal["casepath.strict-utf8-text-sniffer/1.0.0"]
    media_sniffer_sha256: str
    channel: Literal["public-corpus-source-span-loopback-v1"]
    freshness_nonce: str
    acquired_at: str
    expires_at: str
    freshness: Literal["fresh_until_expires_at"]
    receipt_sha256: str

    @model_validator(mode="after")
    def validate_receipt(self) -> "WorkspaceSourceAcquisitionReceiptV1":
        identity = self.model_dump(
            mode="json", exclude={"acquisition_receipt_id", "receipt_sha256", "acquired_at"}
        )
        if (
            self.action_id != f"action.{self.action_sha256}"
            or self.text_end <= self.text_start
            or self.byte_end <= self.byte_start
            or self.byte_end - self.byte_start != self.content_length
            or not all(
                is_sha256(value)
                for value in (
                    self.expected_state_sha256,
                    self.action_sha256,
                    self.adapter_artifact_sha256,
                    self.intent_receipt_sha256,
                    self.claim_registry_watermark_sha256,
                    self.claim_first_seen_receipt_sha256,
                    self.source_entry_sha256,
                    self.source_artifact_sha256,
                    self.content_sha256,
                    self.media_sniffer_sha256,
                    self.freshness_nonce,
                )
            )
            or self.acquisition_receipt_id != "acquisition." + digest_value(identity)
            or _parse_time(self.acquired_at) > _parse_time(self.expires_at)
        ):
            raise ValueError("workspace source acquisition identity is invalid")
        payload = self.model_dump(mode="json", exclude={"receipt_sha256"})
        if self.receipt_sha256 != digest_value(payload):
            raise ValueError("workspace source acquisition self-hash differs")
        return self


class WorkspaceEvidenceRegistrationReceiptV1(FoundationModel):
    contract: Literal["casepath.workspace-evidence-registration-receipt/1.0.0"] = (
        "casepath.workspace-evidence-registration-receipt/1.0.0"
    )
    session_id: str
    loop_id: str
    claim_id: str
    record_version: str
    parent_revision: StrictInt = Field(ge=1)
    parent_state_sha256: str
    action_id: str
    action_sha256: str
    evidence_item_id: str
    idempotency_key: str = Field(min_length=8, max_length=128)
    acquisition_intent_id: str
    intent_receipt_sha256: str
    acquisition_receipt_id: str
    source_acquisition_receipt_sha256: str
    content_sha256: str
    content_length: StrictInt = Field(ge=1, le=MAX_SOURCE_BYTES)
    server_sniffed_media_type: Literal["text/plain; charset=utf-8"]
    media_sniffer_id: Literal["casepath.strict-utf8-text-sniffer/1.0.0"]
    media_sniffer_sha256: str
    channel: Literal["public-corpus-source-span-loopback-v1"]
    freshness_nonce: str
    adapter_id: Literal["loopback-source-byte-acquisition-v1"]
    adapter_artifact_sha256: str
    source_entry_sha256: str
    byte_start: StrictInt = Field(ge=0)
    byte_end: StrictInt = Field(gt=0)
    registered_at: str
    receipt_sha256: str

    @model_validator(mode="after")
    def validate_registration(self) -> "WorkspaceEvidenceRegistrationReceiptV1":
        if (
            self.action_id != f"action.{self.action_sha256}"
            or not all(
                is_sha256(value)
                for value in (
                    self.parent_state_sha256,
                    self.action_sha256,
                    self.intent_receipt_sha256,
                    self.source_acquisition_receipt_sha256,
                    self.content_sha256,
                    self.media_sniffer_sha256,
                    self.freshness_nonce,
                    self.adapter_artifact_sha256,
                    self.source_entry_sha256,
                )
            )
            or self.byte_end <= self.byte_start
            or self.byte_end - self.byte_start != self.content_length
        ):
            raise ValueError("workspace evidence registration identity is invalid")
        payload = self.model_dump(mode="json", exclude={"receipt_sha256"})
        if self.receipt_sha256 != digest_value(payload):
            raise ValueError("workspace evidence registration self-hash differs")
        return self


def _admission(state: ClaimLoopState) -> dict[str, Any]:
    package = state.accepted_artifacts.get("observable_package")
    admission = package.get("workspace_evidence_admission") if isinstance(package, Mapping) else None
    if not isinstance(admission, Mapping):
        raise ClaimLoopError("workspace source admission policy is absent")
    material = dict(admission)
    policy_sha256 = material.pop("policy_sha256", None)
    entries = admission.get("source_entries")
    grants = admission.get("actor_grants")
    expected_policy_keys = {
        "contract",
        "policy_id",
        "source_registry_file_sha256",
        "source_entries",
        "actor_grants",
        "positive_assertion_requires_decision_bearing_grant",
        "operator_note_is_evidence",
        "policy_sha256",
    }
    if (
        set(admission) != expected_policy_keys
        or admission.get("contract")
        != "casepath.workspace-evidence-admission-policy/1.0.0"
        or admission.get("policy_id")
        != "casepath.workspace-handler-source-admission/1.0.0"
        or policy_sha256 != digest_value(material)
        or not is_sha256(admission.get("source_registry_file_sha256"))
        or admission.get("positive_assertion_requires_decision_bearing_grant")
        is not True
        or admission.get("operator_note_is_evidence") is not False
        or not isinstance(entries, list)
        or not entries
        or not isinstance(grants, Mapping)
    ):
        raise ClaimLoopError("workspace source admission policy is invalid")
    seen: set[str] = set()
    expected_entry_keys = {
        "contract",
        "source_kind",
        "support_scope",
        "artifact_id",
        "artifact_sha256",
        "parent_artifact_id",
        "parent_artifact_sha256",
        "representation_identity",
        "source_version",
        "locator_kind",
        "page",
        "text_start",
        "text_end",
        "byte_start",
        "byte_end",
        "exact_text",
        "span_sha256",
        "source_entry_sha256",
    }
    for entry in entries:
        if not isinstance(entry, Mapping) or set(entry) != expected_entry_keys:
            raise ClaimLoopError("workspace source entry is invalid")
        entry_material = dict(entry)
        entry_sha256 = entry_material.pop("source_entry_sha256", None)
        exact_text = entry.get("exact_text")
        if (
            not is_sha256(entry_sha256)
            or entry_sha256 != digest_value(entry_material)
            or entry_sha256 in seen
            or entry.get("source_kind") != "observable_message_span"
            or entry.get("support_scope") != "case_specific"
            or entry.get("locator_kind") != "text_span"
            or entry.get("page") != 1
            or not isinstance(entry.get("byte_start"), int)
            or not isinstance(entry.get("byte_end"), int)
            or int(entry["byte_start"]) < 0
            or int(entry["byte_end"]) <= int(entry["byte_start"])
            or not isinstance(exact_text, str)
            or not exact_text
            or int(entry["byte_end"]) - int(entry["byte_start"])
            != len(exact_text.encode("utf-8"))
            or digest_text(exact_text) != entry.get("span_sha256")
        ):
            raise ClaimLoopError("workspace source entry identity is invalid")
        seen.add(entry_sha256)
    expected_grant_keys = {
        "contract",
        "actor_type",
        "required_process_owner",
        "authority_scope",
        "decision_bearing",
    }
    for evidence_item_id, grant in grants.items():
        if (
            not isinstance(evidence_item_id, str)
            or not isinstance(grant, Mapping)
            or set(grant) != expected_grant_keys
            or grant.get("contract") != "casepath.workspace-actor-grant/1.0.0"
            or grant.get("actor_type") != "claim_handler"
            or not isinstance(grant.get("required_process_owner"), str)
            or grant.get("authority_scope")
            not in {"handler_attested_case_source", "specialist_only"}
            or not isinstance(grant.get("decision_bearing"), bool)
            or (
                grant.get("required_process_owner") == "claim_handler"
            )
            != (
                grant.get("authority_scope")
                == "handler_attested_case_source"
            )
            or (
                grant.get("required_process_owner") == "claim_handler"
            )
            != grant.get("decision_bearing")
            or grant.get("required_process_owner")
            not in {"claim_handler", "external_specialist"}
            or (
                grant.get("required_process_owner") == "external_specialist"
                and grant.get("authority_scope") != "specialist_only"
            )
        ):
            raise ClaimLoopError("workspace actor grant is invalid")
    return dict(admission)


class LoopbackSourceByteAcquisitionAdapterV1:
    """Durable, provider-free acquisition of a server-selected public source span."""

    adapter_id = LOOPBACK_SOURCE_BYTE_ADAPTER_ID
    implementation_id = "casepath.loopback-source-byte-acquisition/1.0.0"

    def __init__(
        self,
        root: str | Path,
        *,
        fault_injector: Callable[[str], None] | None = None,
    ) -> None:
        self.root = Path(root).resolve()
        self._fault_injector = fault_injector
        self.intent_root = self.root / "authority-v3" / "intents"
        self.source_root = self.root / "authority-v3" / "source-blobs"
        self.acquisition_root = self.root / "authority-v3" / "acquisitions"
        self.acquisition_index_root = self.root / "authority-v3" / "acquisition-by-intent"
        self.claim_digest_root = self.root / "authority-v3" / "claim-content-registry"
        self.registration_root = self.root / "authority-v3" / "registrations"
        self.proposal_root = self.root / "authority-v3" / "proposals"
        self.proposal_index_root = self.root / "authority-v3" / "proposal-by-acquisition"
        self.admission_root = self.root / "authority-v3" / "admissions"
        self.admission_index_root = self.root / "authority-v3" / "admission-by-interpretation"
        self.rejection_root = self.root / "authority-v3" / "rejections"
        self.rejection_index_root = self.root / "authority-v3" / "rejection-by-acquisition"
        self.authority_outcome_root = self.root / "authority-v3" / "outcome-by-acquisition"
        self.__authority_writer_capability = object()
        self._authority_source_sha256: str | None = None
        for path in (
            self.intent_root,
            self.source_root,
            self.acquisition_root,
            self.acquisition_index_root,
            self.claim_digest_root,
            self.registration_root,
            self.proposal_root,
            self.proposal_index_root,
            self.admission_root,
            self.admission_index_root,
            self.rejection_root,
            self.rejection_index_root,
            self.authority_outcome_root,
        ):
            _ensure_directory(path)
        self._implementation_source_sha256 = _module_sha256()

    def bind_independent_authority(
        self,
        *,
        authority_id: str,
        authority_source_sha256: str,
    ) -> object:
        if (
            authority_id != "casepath.independent-evidence-authority/1.0.0"
            or not is_sha256(authority_source_sha256)
            or self._authority_source_sha256 is not None
        ):
            raise WorkspaceEvidenceAuthorityError(
                "independent authority writer is invalid or already bound"
            )
        self._authority_source_sha256 = authority_source_sha256
        return self.__authority_writer_capability

    def _assert_authority_writer(
        self,
        *,
        capability: object,
        authority_id: str,
        authority_source_sha256: str,
    ) -> None:
        if (
            capability is not self.__authority_writer_capability
            or authority_id != "casepath.independent-evidence-authority/1.0.0"
            or authority_source_sha256 != self._authority_source_sha256
        ):
            raise WorkspaceEvidenceAuthorityError(
                "authority outcome requires the bound independent verifier"
            )

    def _claim_authority_outcome(
        self,
        *,
        acquisition_receipt_sha256: str,
        decision: str,
        authority_receipt_sha256: str,
    ) -> None:
        material = {
            "contract": "casepath.workspace-authority-outcome-index/1.0.0",
            "acquisition_receipt_sha256": acquisition_receipt_sha256,
            "decision": decision,
            "authority_receipt_sha256": authority_receipt_sha256,
        }
        value = {**material, "receipt_sha256": digest_value(material)}
        path = self.authority_outcome_root / (
            acquisition_receipt_sha256 + ".json"
        )
        if not _publish_new(path, canonical_json_bytes(value)):
            existing = json.loads(_read_regular(path))
            if existing != value:
                raise WorkspaceEvidenceAuthorityError(
                    "acquisition already has a different authority outcome"
                )

    def _authority_outcome(self, acquisition_receipt_sha256: str) -> dict[str, Any]:
        path = self.authority_outcome_root / (
            acquisition_receipt_sha256 + ".json"
        )
        if not path.exists():
            raise WorkspaceEvidenceAuthorityError(
                "acquisition authority outcome is absent"
            )
        value = json.loads(_read_regular(path))
        material = {
            key: item for key, item in value.items() if key != "receipt_sha256"
        }
        if (
            set(value)
            != {
                "contract",
                "acquisition_receipt_sha256",
                "decision",
                "authority_receipt_sha256",
                "receipt_sha256",
            }
            or value.get("contract")
            != "casepath.workspace-authority-outcome-index/1.0.0"
            or value.get("acquisition_receipt_sha256")
            != acquisition_receipt_sha256
            or value.get("decision") not in {"admitted", "rejected"}
            or not is_sha256(value.get("authority_receipt_sha256"))
            or value.get("receipt_sha256") != digest_value(material)
        ):
            raise WorkspaceEvidenceAuthorityError(
                "acquisition authority outcome is invalid"
            )
        return value

    def _fault(self, boundary: str) -> None:
        if self._fault_injector is not None:
            self._fault_injector(boundary)

    @staticmethod
    def _stable_receipt_identity(value: FoundationModel, *volatile: str) -> dict[str, Any]:
        return value.model_dump(mode="json", exclude=set(volatile))

    def _source_path(self, *, claim_id: str, content_sha256: str) -> Path:
        return self.source_root / sha256(claim_id.encode("utf-8")).hexdigest() / (
            content_sha256 + ".bin"
        )

    def _publish_source_blob(self, *, claim_id: str, content_sha256: str, raw: bytes) -> None:
        path = self._source_path(claim_id=claim_id, content_sha256=content_sha256)
        _ensure_directory(path.parent)
        if path.exists():
            if _read_regular(path) != raw:
                raise WorkspaceEvidenceAuthorityError("source blob digest collision")
            return
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb", closefd=True) as handle:
                handle.write(raw)
                handle.flush()
                self._fault("BEFORE_SOURCE_BLOB_FSYNC")
                os.fsync(handle.fileno())
                self._fault("AFTER_SOURCE_BLOB_FSYNC")
            self._fault("BEFORE_SOURCE_BLOB_RENAME")
            if path.exists():
                if _read_regular(path) != raw:
                    raise WorkspaceEvidenceAuthorityError("source blob digest collision")
            else:
                os.replace(temporary, path)
                _fsync_directory(path.parent)
            self._fault("AFTER_SOURCE_BLOB_RENAME")
        finally:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass
            _fsync_directory(path.parent)

    def _claim_registry_watermark(self, claim_id: str) -> str:
        root = self.claim_digest_root / sha256(claim_id.encode("utf-8")).hexdigest()
        if not root.exists():
            return digest_value([])
        entries: list[dict[str, Any]] = []
        for path in sorted(root.glob("*.json")):
            value = json.loads(_read_regular(path))
            receipt_sha256 = value.get("receipt_sha256")
            if (
                not isinstance(value, dict)
                or not is_sha256(receipt_sha256)
                or receipt_sha256
                != digest_value({key: item for key, item in value.items() if key != "receipt_sha256"})
                or value.get("claim_id") != claim_id
            ):
                raise WorkspaceEvidenceAuthorityError("claim content registry is invalid")
            entries.append(value)
        return digest_value(entries)

    def _reserve_claim_content(
        self,
        *,
        intent: WorkspaceAcquisitionIntentV1,
        source_entry_sha256: str,
        content_sha256: str,
    ) -> dict[str, Any]:
        root = self.claim_digest_root / sha256(intent.claim_id.encode("utf-8")).hexdigest()
        path = root / (content_sha256 + ".json")
        material = {
            "contract": "casepath.workspace-claim-content-first-seen/1.0.0",
            "claim_id": intent.claim_id,
            "content_sha256": content_sha256,
            "acquisition_intent_id": intent.intent_id,
            "intent_receipt_sha256": intent.receipt_sha256,
            "claim_registry_watermark_sha256": intent.claim_registry_watermark_sha256,
            "source_entry_sha256": source_entry_sha256,
            "first_seen_at": intent.issued_at,
        }
        value = {**material, "receipt_sha256": digest_value(material)}
        if not _publish_new(path, canonical_json_bytes(value)):
            existing = json.loads(_read_regular(path))
            if existing != value:
                self._reject(
                    "acquisition",
                    {
                        "claim_id": intent.claim_id,
                        "intent_id": intent.intent_id,
                        "content_sha256": content_sha256,
                    },
                    "preexisting claim digest cannot be acquired as new",
                )
            return existing
        return value

    def _claim_content_reservation(
        self, *, claim_id: str, content_sha256: str
    ) -> dict[str, Any] | None:
        path = (
            self.claim_digest_root
            / sha256(claim_id.encode("utf-8")).hexdigest()
            / (content_sha256 + ".json")
        )
        if not path.exists():
            return None
        value = json.loads(_read_regular(path))
        material = {key: item for key, item in value.items() if key != "receipt_sha256"}
        if (
            value.get("claim_id") != claim_id
            or value.get("content_sha256") != content_sha256
            or value.get("receipt_sha256") != digest_value(material)
        ):
            raise WorkspaceEvidenceAuthorityError("claim content reservation is invalid")
        return value

    @property
    def implementation_source_sha256(self) -> str:
        if _module_sha256() != self._implementation_source_sha256:
            raise WorkspaceEvidenceAuthorityError("loopback adapter source changed")
        return self._implementation_source_sha256

    @property
    def implementation_sha256(self) -> str:
        return adapter_implementation_sha256_v1(
            adapter_id=self.adapter_id,
            implementation_id=self.implementation_id,
            implementation_source_sha256=self.implementation_source_sha256,
        )

    @property
    def adapter_artifact_sha256(self) -> str:
        return digest_value(
            {
                "contract": "casepath.loopback-adapter-artifact/1.0.0",
                "adapter_id": self.adapter_id,
                "implementation_id": self.implementation_id,
                "implementation_source_sha256": self.implementation_source_sha256,
                "channel": SOURCE_ACQUISITION_CHANNEL,
            }
        )

    def _record_rejection(self, phase: str, context: Mapping[str, Any], reason: str) -> None:
        material = {
            "contract": "casepath.workspace-evidence-rejection/1.0.0",
            "phase": phase,
            "context": dict(context),
            "reason": reason[:300],
            "authoritative_state_effect": False,
        }
        receipt = {**material, "receipt_sha256": digest_value(material)}
        self._fault("BEFORE_REJECTION_APPEND")
        _publish_new(
            self.rejection_root / (receipt["receipt_sha256"] + ".json"),
            canonical_json_bytes(receipt),
        )
        self._fault("AFTER_REJECTION_APPEND")

    def _reject(self, phase: str, context: Mapping[str, Any], reason: str) -> None:
        self._record_rejection(phase, context, reason)
        raise WorkspaceEvidenceAuthorityError(reason)

    def record_authority_rejection(
        self,
        *,
        capability: object,
        authority_id: str,
        authority_source_sha256: str,
        action: EvidenceAction,
        state: ClaimLoopState,
        acquisition: AcquisitionReceiptV1,
        reason: str,
    ) -> dict[str, Any]:
        self._assert_authority_writer(
            capability=capability,
            authority_id=authority_id,
            authority_source_sha256=authority_source_sha256,
        )
        proposal_sha256: str | None = None
        try:
            proposal_sha256 = str(
                self.proposal_for_acquisition(acquisition.receipt_sha256)[
                    "proposal_sha256"
                ]
            )
        except (KeyError, OSError, TypeError, ValueError):
            proposal_sha256 = None
        receipt: WorkspaceSourceAcquisitionReceiptV1 | None = None
        try:
            receipt, _ = self.binding_for_acquisition(acquisition=acquisition)
        except (OSError, TypeError, ValueError):
            receipt = None
        material = {
            "contract": "casepath.workspace-authority-rejection/1.0.0",
            "session_id": state.session_id,
            "loop_id": state.loop_id,
            "claim_id": state.claim_id,
            "record_version": state.record_version,
            "parent_revision": state.revision,
            "parent_state_sha256": state.state_sha256,
            "action_id": action.action_id,
            "action_sha256": action.action_sha256,
            "dispatch_sha256": state.active_dispatch_sha256,
            "acquisition_receipt_sha256": acquisition.receipt_sha256,
            "acquisition_intent_id": (
                receipt.acquisition_intent_id if receipt is not None else None
            ),
            "source_acquisition_receipt_sha256": (
                receipt.receipt_sha256 if receipt is not None else None
            ),
            "source_entry_sha256": (
                receipt.source_entry_sha256 if receipt is not None else None
            ),
            "content_sha256": receipt.content_sha256 if receipt is not None else None,
            "proposal_sha256": proposal_sha256,
            "authority_id": authority_id,
            "authority_source_sha256": authority_source_sha256,
            "reason": reason[:300],
            "rejected_at": acquisition.acquired_at,
            "authoritative_semantic_effect": False,
        }
        value = {**material, "receipt_sha256": digest_value(material)}
        path = self.rejection_root / (value["receipt_sha256"] + ".json")
        self._claim_authority_outcome(
            acquisition_receipt_sha256=acquisition.receipt_sha256,
            decision="rejected",
            authority_receipt_sha256=value["receipt_sha256"],
        )
        self._fault("BEFORE_REJECTION_APPEND")
        if not _publish_new(path, canonical_json_bytes(value)):
            if json.loads(_read_regular(path)) != value:
                raise WorkspaceEvidenceAuthorityError("authority rejection collision")
        index_material = {
            "contract": "casepath.workspace-rejection-acquisition-index/1.0.0",
            "acquisition_receipt_sha256": acquisition.receipt_sha256,
            "rejection_receipt_sha256": value["receipt_sha256"],
        }
        index = {**index_material, "receipt_sha256": digest_value(index_material)}
        index_path = self.rejection_index_root / (acquisition.receipt_sha256 + ".json")
        if not _publish_new(index_path, canonical_json_bytes(index)):
            if json.loads(_read_regular(index_path)) != index:
                raise WorkspaceEvidenceAuthorityError(
                    "acquisition has multiple authority rejection outcomes"
                )
        self._fault("AFTER_REJECTION_APPEND")
        return value

    def authority_rejection(self, acquisition_receipt_sha256: str) -> dict[str, Any]:
        index_path = self.rejection_index_root / (acquisition_receipt_sha256 + ".json")
        if not index_path.exists():
            raise WorkspaceEvidenceAuthorityError("authority rejection receipt is absent")
        index = json.loads(_read_regular(index_path))
        index_material = {key: value for key, value in index.items() if key != "receipt_sha256"}
        if index.get("receipt_sha256") != digest_value(index_material):
            raise WorkspaceEvidenceAuthorityError("authority rejection index is invalid")
        path = self.rejection_root / (str(index["rejection_receipt_sha256"]) + ".json")
        value = json.loads(_read_regular(path))
        material = {key: item for key, item in value.items() if key != "receipt_sha256"}
        expected_keys = {
            "contract",
            "session_id",
            "loop_id",
            "claim_id",
            "record_version",
            "parent_revision",
            "parent_state_sha256",
            "action_id",
            "action_sha256",
            "dispatch_sha256",
            "acquisition_receipt_sha256",
            "acquisition_intent_id",
            "source_acquisition_receipt_sha256",
            "source_entry_sha256",
            "content_sha256",
            "proposal_sha256",
            "authority_id",
            "authority_source_sha256",
            "reason",
            "rejected_at",
            "authoritative_semantic_effect",
            "receipt_sha256",
        }
        if (
            set(value) != expected_keys
            or value.get("contract")
            != "casepath.workspace-authority-rejection/1.0.0"
            or value.get("receipt_sha256") != index["rejection_receipt_sha256"]
            or value.get("acquisition_receipt_sha256")
            != acquisition_receipt_sha256
            or value.get("receipt_sha256") != digest_value(material)
            or value.get("authority_id")
            != "casepath.independent-evidence-authority/1.0.0"
            or value.get("authority_source_sha256")
            != self._authority_source_sha256
            or value.get("authoritative_semantic_effect") is not False
        ):
            raise WorkspaceEvidenceAuthorityError("authority rejection receipt is invalid")
        outcome = self._authority_outcome(acquisition_receipt_sha256)
        if (
            outcome.get("decision") != "rejected"
            or outcome.get("authority_receipt_sha256") != value["receipt_sha256"]
        ):
            raise WorkspaceEvidenceAuthorityError(
                "authority rejection is not the exclusive acquisition outcome"
            )
        return value

    def rejected_source_entry_sha256s(
        self, *, claim_id: str, action_id: str
    ) -> frozenset[str]:
        rejected: set[str] = set()
        for path in self.rejection_index_root.glob("*.json"):
            acquisition_sha256 = path.stem
            if not is_sha256(acquisition_sha256):
                raise WorkspaceEvidenceAuthorityError(
                    "authority rejection index filename is invalid"
                )
            value = self.authority_rejection(acquisition_sha256)
            source_entry_sha256 = value.get("source_entry_sha256")
            if (
                value.get("claim_id") == claim_id
                and value.get("action_id") == action_id
                and source_entry_sha256 is not None
            ):
                if not is_sha256(source_entry_sha256):
                    raise WorkspaceEvidenceAuthorityError(
                        "authority rejection source entry is invalid"
                    )
                rejected.add(source_entry_sha256)
        return frozenset(rejected)

    def mint_intent(
        self,
        *,
        state: ClaimLoopState,
        action: EvidenceAction,
        idempotency_key: str,
        timestamp: str | None = None,
    ) -> WorkspaceAcquisitionIntentV1:
        issued_at, instant = _now(timestamp)
        if (
            state.selected_action != action
            or state.active_dispatch_sha256 is not None
            or not 8 <= len(idempotency_key) <= 128
        ):
            self._reject("intent", {"claim_id": state.claim_id}, "acquisition intent is not bound to an idle selected action")
        payload = {
            "contract": "casepath.workspace-acquisition-intent/1.0.0",
            "session_id": state.session_id,
            "loop_id": state.loop_id,
            "claim_id": state.claim_id,
            "record_version": state.record_version,
            "expected_revision": state.revision,
            "expected_state_sha256": state.state_sha256,
            "action_id": action.action_id,
            "action_sha256": action.action_sha256,
            "evidence_item_id": action.evidence_item_id,
            "idempotency_key": idempotency_key,
            "adapter_id": self.adapter_id,
            "claim_registry_watermark_sha256": self._claim_registry_watermark(
                state.claim_id
            ),
            "issued_at": issued_at,
            "expires_at": (instant + timedelta(seconds=INTENT_TTL_SECONDS)).isoformat(),
        }
        identity = {
            key: value
            for key, value in payload.items()
            if key not in {"issued_at", "expires_at"}
        }
        intent_id = "intent." + digest_value(identity)
        path = self.intent_root / _resource_name(intent_id)
        if path.exists():
            existing = WorkspaceAcquisitionIntentV1.model_validate_json(_read_regular(path))
            stable = existing.model_dump(
                mode="json",
                exclude={"issued_at", "expires_at", "receipt_sha256", "intent_id"},
            )
            requested = identity
            if stable != requested:
                self._reject("intent", {"intent_id": intent_id}, "acquisition intent replay differs")
            return existing
        intent_payload = {**payload, "intent_id": intent_id}
        intent = WorkspaceAcquisitionIntentV1.model_validate(
            {**intent_payload, "receipt_sha256": digest_value(intent_payload)}
        )
        if not _publish_new(path, canonical_json_bytes(intent.model_dump(mode="json"))):
            existing = WorkspaceAcquisitionIntentV1.model_validate_json(_read_regular(path))
            if self._stable_receipt_identity(
                existing, "issued_at", "expires_at", "receipt_sha256"
            ) != self._stable_receipt_identity(
                intent, "issued_at", "expires_at", "receipt_sha256"
            ):
                self._reject("intent", {"intent_id": intent_id}, "acquisition intent collision")
            return existing
        return intent

    def intent(self, intent_id: str) -> WorkspaceAcquisitionIntentV1:
        path = self.intent_root / _resource_name(intent_id)
        if not path.exists():
            raise WorkspaceEvidenceAuthorityError("acquisition intent does not exist")
        value = WorkspaceAcquisitionIntentV1.model_validate_json(_read_regular(path))
        if value.intent_id != intent_id:
            raise WorkspaceEvidenceAuthorityError("acquisition intent lookup differs")
        return value

    def intent_replay(
        self,
        *,
        claim_id: str,
        action_id: str,
        expected_revision: int,
        idempotency_key: str,
    ) -> WorkspaceAcquisitionIntentV1 | None:
        matches: list[WorkspaceAcquisitionIntentV1] = []
        for path in self.intent_root.glob("*.json"):
            value = WorkspaceAcquisitionIntentV1.model_validate_json(_read_regular(path))
            if (
                value.claim_id == claim_id
                and value.action_id == action_id
                and value.expected_revision == expected_revision
                and value.idempotency_key == idempotency_key
            ):
                matches.append(value)
        if len(matches) > 1:
            raise WorkspaceEvidenceAuthorityError("acquisition intent replay is ambiguous")
        return matches[0] if matches else None

    def recoverable_acquisition(
        self,
        *,
        state: ClaimLoopState,
        action: EvidenceAction,
    ) -> tuple[
        WorkspaceAcquisitionIntentV1,
        WorkspaceSourceAcquisitionReceiptV1,
        bytes,
    ] | None:
        """Return one durable, unregistered acquisition for the exact parent.

        Browser command storage is only a retry convenience. Once acquisition
        has durably committed, its server-owned receipt remains the authority
        for recovering the same intent and idempotency context after a renderer
        crash or cleared session storage. A fresh intent must never relabel
        those already-first-seen bytes as new.
        """

        matches: list[
            tuple[
                WorkspaceAcquisitionIntentV1,
                WorkspaceSourceAcquisitionReceiptV1,
                bytes,
            ]
        ] = []
        for path in self.acquisition_root.glob("*.json"):
            receipt = WorkspaceSourceAcquisitionReceiptV1.model_validate_json(
                _read_regular(path)
            )
            if (
                receipt.session_id != state.session_id
                or receipt.loop_id != state.loop_id
                or receipt.claim_id != state.claim_id
                or receipt.record_version != state.record_version
                or receipt.expected_revision != state.revision
                or receipt.expected_state_sha256 != state.state_sha256
                or receipt.action_id != action.action_id
                or receipt.action_sha256 != action.action_sha256
                or receipt.evidence_item_id != action.evidence_item_id
            ):
                continue
            if self.staged(
                session_id=state.session_id,
                loop_id=state.loop_id,
                parent_revision=state.revision,
                action_sha256=action.action_sha256,
            ) is not None:
                continue
            intent = self.intent(receipt.acquisition_intent_id)
            self._validate_intent_state(
                intent,
                state=state,
                action=action,
                instant=_parse_time(receipt.acquired_at),
                enforce_expiry=True,
            )
            replay = self.acquisition_for_intent(intent.intent_id)
            if replay is None or replay[0] != receipt:
                raise WorkspaceEvidenceAuthorityError(
                    "durable acquisition recovery binding differs"
                )
            matches.append((intent, receipt, replay[1]))
        if len(matches) > 1:
            raise WorkspaceEvidenceAuthorityError(
                "durable acquisition recovery is ambiguous"
            )
        return matches[0] if matches else None

    def acquisition_for_intent(
        self, intent_id: str
    ) -> tuple[WorkspaceSourceAcquisitionReceiptV1, bytes] | None:
        index_path = self.acquisition_index_root / _resource_name(intent_id)
        receipt: WorkspaceSourceAcquisitionReceiptV1 | None = None
        if index_path.exists():
            index = json.loads(_read_regular(index_path))
            payload = {key: value for key, value in index.items() if key != "receipt_sha256"}
            if (
                index.get("contract")
                != "casepath.workspace-acquisition-intent-index/1.0.0"
                or index.get("acquisition_intent_id") != intent_id
                or index.get("receipt_sha256") != digest_value(payload)
            ):
                raise WorkspaceEvidenceAuthorityError("acquisition intent index is invalid")
            receipt = self.acquisition_receipt(str(index["acquisition_receipt_id"]))
            if (
                receipt.acquisition_intent_id != intent_id
                or index.get("source_acquisition_receipt_sha256")
                != receipt.receipt_sha256
            ):
                raise WorkspaceEvidenceAuthorityError(
                    "acquisition intent index receipt binding differs"
                )
        else:
            matches = [
                WorkspaceSourceAcquisitionReceiptV1.model_validate_json(
                    _read_regular(path)
                )
                for path in self.acquisition_root.glob("*.json")
            ]
            matches = [value for value in matches if value.acquisition_intent_id == intent_id]
            if len(matches) > 1:
                raise WorkspaceEvidenceAuthorityError("acquisition intent has multiple receipts")
            if matches:
                receipt = matches[0]
                material = {
                    "contract": "casepath.workspace-acquisition-intent-index/1.0.0",
                    "acquisition_intent_id": intent_id,
                    "acquisition_receipt_id": receipt.acquisition_receipt_id,
                    "source_acquisition_receipt_sha256": receipt.receipt_sha256,
                }
                index = {**material, "receipt_sha256": digest_value(material)}
                if not _publish_new(index_path, canonical_json_bytes(index)):
                    existing = json.loads(_read_regular(index_path))
                    if existing != index:
                        raise WorkspaceEvidenceAuthorityError(
                            "acquisition intent index collision"
                        )
        if receipt is None:
            return None
        raw = _read_regular(
            self._source_path(
                claim_id=receipt.claim_id, content_sha256=receipt.content_sha256
            )
        )
        if receipt.content_sha256 != sha256(raw).hexdigest() or receipt.content_length != len(raw):
            raise WorkspaceEvidenceAuthorityError("acquisition source blob differs")
        return receipt, raw

    @staticmethod
    def _validate_intent_state(
        intent: WorkspaceAcquisitionIntentV1,
        *,
        state: ClaimLoopState,
        action: EvidenceAction,
        instant: datetime,
        enforce_expiry: bool = True,
    ) -> None:
        if (
            intent.session_id != state.session_id
            or intent.loop_id != state.loop_id
            or intent.claim_id != state.claim_id
            or intent.record_version != state.record_version
            or intent.expected_revision != state.revision
            or intent.expected_state_sha256 != state.state_sha256
            or intent.action_id != action.action_id
            or intent.action_sha256 != action.action_sha256
            or intent.evidence_item_id != action.evidence_item_id
            or intent.adapter_id != LOOPBACK_SOURCE_BYTE_ADAPTER_ID
            or (enforce_expiry and instant > _parse_time(intent.expires_at))
        ):
            raise WorkspaceEvidenceAuthorityError("acquisition intent is stale, expired, or cross-bound")

    def acquire(
        self,
        *,
        state: ClaimLoopState,
        action: EvidenceAction,
        intent_id: str,
        source_entry: Mapping[str, Any],
        timestamp: str | None = None,
    ) -> tuple[WorkspaceSourceAcquisitionReceiptV1, bytes]:
        replay = self.acquisition_for_intent(intent_id)
        if replay is not None:
            receipt, raw = replay
            try:
                intent = self.intent(intent_id)
                self._validate_intent_state(
                    intent,
                    state=state,
                    action=action,
                    instant=_parse_time(receipt.acquired_at),
                    enforce_expiry=False,
                )
            except (TypeError, ValueError, WorkspaceEvidenceAuthorityError) as exc:
                self._reject(
                    "acquisition",
                    {"intent_id": intent_id},
                    f"acquisition replay intent is invalid: {exc}",
                )
            if (
                receipt.acquisition_intent_id != intent.intent_id
                or receipt.intent_receipt_sha256 != intent.receipt_sha256
                or receipt.session_id != state.session_id
                or receipt.loop_id != state.loop_id
                or receipt.claim_id != state.claim_id
                or receipt.record_version != state.record_version
                or receipt.expected_revision != state.revision
                or receipt.expected_state_sha256 != state.state_sha256
                or receipt.action_id != action.action_id
                or receipt.action_sha256 != action.action_sha256
                or receipt.evidence_item_id != action.evidence_item_id
                or receipt.idempotency_key != intent.idempotency_key
            ):
                self._reject("acquisition", {"intent_id": intent_id}, "acquisition replay is cross-bound")
            return receipt, raw
        acquired_at, instant = _now(timestamp)
        try:
            intent = self.intent(intent_id)
            self._validate_intent_state(
                intent,
                state=state,
                action=action,
                instant=instant,
                enforce_expiry=True,
            )
            exact_text = source_entry["exact_text"]
            if not isinstance(exact_text, str):
                raise WorkspaceEvidenceAuthorityError("loopback source text is invalid")
            raw = exact_text.encode("utf-8")
            decoded = raw.decode("utf-8", errors="strict")
            if (
                not raw
                or len(raw) > MAX_SOURCE_BYTES
                or b"\x00" in raw
                or decoded != unicodedata.normalize("NFC", decoded)
                or source_entry.get("source_entry_sha256") is None
                or digest_text(decoded) != source_entry.get("span_sha256")
                or len(decoded)
                != int(source_entry["text_end"]) - int(source_entry["text_start"])
                or len(raw)
                != int(source_entry["byte_end"]) - int(source_entry["byte_start"])
            ):
                raise WorkspaceEvidenceAuthorityError("loopback source bytes are malformed or unsupported")
            content_sha256 = sha256(raw).hexdigest()
            reservation = self._claim_content_reservation(
                claim_id=state.claim_id, content_sha256=content_sha256
            )
            if instant > _parse_time(intent.expires_at) and (
                reservation is None
                or reservation.get("acquisition_intent_id") != intent.intent_id
                or reservation.get("source_entry_sha256")
                != source_entry["source_entry_sha256"]
            ):
                raise WorkspaceEvidenceAuthorityError("acquisition intent is expired")
            if reservation is not None and instant > _parse_time(intent.expires_at):
                acquired_at = str(reservation["first_seen_at"])
        except (KeyError, TypeError, UnicodeError, ValueError, WorkspaceEvidenceAuthorityError) as exc:
            self._reject("acquisition", {"intent_id": intent_id}, str(exc))
        first_seen = self._reserve_claim_content(
            intent=intent,
            source_entry_sha256=str(source_entry["source_entry_sha256"]),
            content_sha256=content_sha256,
        )
        freshness_nonce = digest_value(
            {
                "intent_receipt_sha256": intent.receipt_sha256,
                "source_entry_sha256": source_entry["source_entry_sha256"],
                "claim_first_seen_receipt_sha256": first_seen["receipt_sha256"],
            }
        )
        identity = {
            "contract": "casepath.workspace-source-acquisition/1.0.0",
            "acquisition_intent_id": intent.intent_id,
            "intent_receipt_sha256": intent.receipt_sha256,
            "session_id": state.session_id,
            "loop_id": state.loop_id,
            "claim_id": state.claim_id,
            "record_version": state.record_version,
            "expected_revision": state.revision,
            "expected_state_sha256": state.state_sha256,
            "action_id": action.action_id,
            "action_sha256": action.action_sha256,
            "evidence_item_id": action.evidence_item_id,
            "idempotency_key": intent.idempotency_key,
            "adapter_id": self.adapter_id,
            "adapter_artifact_sha256": self.adapter_artifact_sha256,
            "claim_registry_watermark_sha256": intent.claim_registry_watermark_sha256,
            "claim_first_seen_receipt_sha256": first_seen["receipt_sha256"],
            "source_entry_sha256": str(source_entry["source_entry_sha256"]),
            "source_artifact_id": str(source_entry["artifact_id"]),
            "source_artifact_sha256": str(source_entry["artifact_sha256"]),
            "source_version": str(source_entry["source_version"]),
            "text_start": int(source_entry["text_start"]),
            "text_end": int(source_entry["text_end"]),
            "byte_start": int(source_entry["byte_start"]),
            "byte_end": int(source_entry["byte_end"]),
            "content_sha256": content_sha256,
            "content_length": len(raw),
            "server_sniffed_media_type": "text/plain; charset=utf-8",
            "media_sniffer_id": SOURCE_MEDIA_SNIFFER_ID,
            "media_sniffer_sha256": SOURCE_MEDIA_SNIFFER_SHA256,
            "channel": SOURCE_ACQUISITION_CHANNEL,
            "freshness_nonce": freshness_nonce,
            "expires_at": intent.expires_at,
            "freshness": "fresh_until_expires_at",
        }
        receipt_id = "acquisition." + digest_value(identity)
        path = self.acquisition_root / _resource_name(receipt_id)
        if path.exists():
            existing = WorkspaceSourceAcquisitionReceiptV1.model_validate_json(_read_regular(path))
            if existing.acquisition_receipt_id != receipt_id:
                self._reject("acquisition", {"intent_id": intent_id}, "acquisition replay identity differs")
            stored = _read_regular(
                self._source_path(claim_id=state.claim_id, content_sha256=content_sha256)
            )
            if stored != raw:
                self._reject("acquisition", {"intent_id": intent_id}, "acquisition replay bytes differ")
            return existing, stored
        self._publish_source_blob(
            claim_id=state.claim_id, content_sha256=content_sha256, raw=raw
        )
        receipt_payload = {
            **identity,
            "acquisition_receipt_id": receipt_id,
            "acquired_at": acquired_at,
        }
        receipt = WorkspaceSourceAcquisitionReceiptV1.model_validate(
            {**receipt_payload, "receipt_sha256": digest_value(receipt_payload)}
        )
        self._fault("BEFORE_ACQUISITION_RECEIPT_APPEND")
        if not _publish_new(path, canonical_json_bytes(receipt.model_dump(mode="json"))):
            existing = WorkspaceSourceAcquisitionReceiptV1.model_validate_json(_read_regular(path))
            if self._stable_receipt_identity(
                existing, "acquired_at", "receipt_sha256"
            ) != self._stable_receipt_identity(receipt, "acquired_at", "receipt_sha256"):
                self._reject("acquisition", {"intent_id": intent_id}, "acquisition receipt collision")
            receipt = existing
        self._fault("AFTER_ACQUISITION_RECEIPT_APPEND")
        replay = self.acquisition_for_intent(intent_id)
        if replay is None:
            raise WorkspaceEvidenceAuthorityError("acquisition receipt index is absent")
        return replay

    def acquisition_receipt(self, receipt_id: str) -> WorkspaceSourceAcquisitionReceiptV1:
        path = self.acquisition_root / _resource_name(receipt_id)
        if not path.exists():
            raise WorkspaceEvidenceAuthorityError("acquisition receipt does not exist")
        value = WorkspaceSourceAcquisitionReceiptV1.model_validate_json(_read_regular(path))
        if value.acquisition_receipt_id != receipt_id:
            raise WorkspaceEvidenceAuthorityError("acquisition receipt lookup differs")
        return value

    @staticmethod
    def _registration_identity(
        *, session_id: str, loop_id: str, parent_revision: int, action_sha256: str
    ) -> str:
        return digest_value(
            {
                "contract": "casepath.workspace-evidence-registration-resource/1.0.0",
                "session_id": session_id,
                "loop_id": loop_id,
                "parent_revision": parent_revision,
                "action_sha256": action_sha256,
            }
        )

    def _registration_path(
        self, *, session_id: str, loop_id: str, parent_revision: int, action_sha256: str
    ) -> Path:
        return self.registration_root / (
            self._registration_identity(
                session_id=session_id,
                loop_id=loop_id,
                parent_revision=parent_revision,
                action_sha256=action_sha256,
            )
            + ".json"
        )

    def register(
        self,
        *,
        state: ClaimLoopState,
        action: EvidenceAction,
        schema: str,
        expected_revision: int,
        idempotency_key: str,
        acquisition_intent_id: str,
        acquisition_receipt_id: str,
        content_b64: str,
        timestamp: str | None = None,
    ) -> WorkspaceEvidenceRegistrationReceiptV1:
        registered_at, _instant = _now(timestamp)
        path = self._registration_path(
            session_id=state.session_id,
            loop_id=state.loop_id,
            parent_revision=expected_revision,
            action_sha256=action.action_sha256,
        )
        context = {
            "claim_id": state.claim_id,
            "action_id": action.action_id,
            "expected_revision": expected_revision,
            "acquisition_intent_id": acquisition_intent_id,
            "acquisition_receipt_id": acquisition_receipt_id,
        }
        try:
            raw = decode_canonical_content_b64(content_b64)
            intent = self.intent(acquisition_intent_id)
            acquisition = self.acquisition_receipt(acquisition_receipt_id)
            if path.exists():
                existing = WorkspaceEvidenceRegistrationReceiptV1.model_validate_json(
                    _read_regular(path)
                )
                if (
                    schema == EVIDENCE_REGISTRATION_SCHEMA
                    and existing.claim_id == state.claim_id
                    and existing.action_id == action.action_id
                    and existing.parent_revision == expected_revision
                    and existing.idempotency_key == idempotency_key
                    and existing.acquisition_intent_id == acquisition_intent_id
                    and existing.acquisition_receipt_id == acquisition_receipt_id
                    and existing.content_sha256 == sha256(raw).hexdigest()
                    and existing.content_length == len(raw)
                ):
                    return existing
                raise WorkspaceEvidenceAuthorityError(
                    "evidence action was registered with different input"
                )
            if (
                schema != EVIDENCE_REGISTRATION_SCHEMA
                or state.selected_action != action
                or state.active_dispatch_sha256 is not None
                or expected_revision != state.revision
                or intent.idempotency_key != idempotency_key
            ):
                raise WorkspaceEvidenceAuthorityError("evidence registration is stale or unsupported")
            self._validate_intent_state(
                intent,
                state=state,
                action=action,
                # Acquisition is the durable external effect. A later retry
                # may finish registration after wall-clock expiry only when
                # this receipt proves the exact acquisition occurred while
                # its intent was still live.
                instant=_parse_time(acquisition.acquired_at),
                enforce_expiry=True,
            )
            raw_sha256 = sha256(raw).hexdigest()
            stable = {
                "acquisition_intent_id": acquisition_intent_id,
                "session_id": state.session_id,
                "loop_id": state.loop_id,
                "claim_id": state.claim_id,
                "record_version": state.record_version,
                "expected_revision": state.revision,
                "expected_state_sha256": state.state_sha256,
                "action_id": action.action_id,
                "action_sha256": action.action_sha256,
                "evidence_item_id": action.evidence_item_id,
                "idempotency_key": idempotency_key,
                "adapter_id": self.adapter_id,
                "adapter_artifact_sha256": self.adapter_artifact_sha256,
            }
            if any(getattr(acquisition, key) != value for key, value in stable.items()):
                raise WorkspaceEvidenceAuthorityError("acquisition receipt is cross-bound or substituted")
            if (
                acquisition.content_sha256 != raw_sha256
                or acquisition.content_length != len(raw)
                or acquisition.server_sniffed_media_type != "text/plain; charset=utf-8"
                or acquisition.media_sniffer_id != SOURCE_MEDIA_SNIFFER_ID
                or acquisition.media_sniffer_sha256 != SOURCE_MEDIA_SNIFFER_SHA256
                or acquisition.channel != SOURCE_ACQUISITION_CHANNEL
                or acquisition.freshness != "fresh_until_expires_at"
                or _read_regular(
                    self._source_path(claim_id=state.claim_id, content_sha256=raw_sha256)
                )
                != raw
            ):
                raise WorkspaceEvidenceAuthorityError("registered bytes differ from the fresh acquisition receipt")
        except (OSError, TypeError, ValueError, WorkspaceEvidenceAuthorityError) as exc:
            self._reject("registration", context, str(exc))
        payload = {
            "contract": "casepath.workspace-evidence-registration-receipt/1.0.0",
            "session_id": state.session_id,
            "loop_id": state.loop_id,
            "claim_id": state.claim_id,
            "record_version": state.record_version,
            "parent_revision": state.revision,
            "parent_state_sha256": state.state_sha256,
            "action_id": action.action_id,
            "action_sha256": action.action_sha256,
            "evidence_item_id": action.evidence_item_id,
            "idempotency_key": idempotency_key,
            "acquisition_intent_id": acquisition_intent_id,
            "intent_receipt_sha256": intent.receipt_sha256,
            "acquisition_receipt_id": acquisition_receipt_id,
            "source_acquisition_receipt_sha256": acquisition.receipt_sha256,
            "content_sha256": acquisition.content_sha256,
            "content_length": acquisition.content_length,
            "server_sniffed_media_type": acquisition.server_sniffed_media_type,
            "media_sniffer_id": acquisition.media_sniffer_id,
            "media_sniffer_sha256": acquisition.media_sniffer_sha256,
            "channel": acquisition.channel,
            "freshness_nonce": acquisition.freshness_nonce,
            "adapter_id": acquisition.adapter_id,
            "adapter_artifact_sha256": acquisition.adapter_artifact_sha256,
            "source_entry_sha256": acquisition.source_entry_sha256,
            "byte_start": acquisition.byte_start,
            "byte_end": acquisition.byte_end,
            "registered_at": registered_at,
        }
        receipt = WorkspaceEvidenceRegistrationReceiptV1.model_validate(
            {**payload, "receipt_sha256": digest_value(payload)}
        )
        self._fault("BEFORE_REGISTRATION_RECEIPT_APPEND")
        if not _publish_new(path, canonical_json_bytes(receipt.model_dump(mode="json"))):
            existing = WorkspaceEvidenceRegistrationReceiptV1.model_validate_json(_read_regular(path))
            if self._stable_receipt_identity(
                existing, "registered_at", "receipt_sha256"
            ) != self._stable_receipt_identity(
                receipt, "registered_at", "receipt_sha256"
            ):
                self._reject("registration", context, "evidence registration collision")
            receipt = existing
        self._fault("AFTER_REGISTRATION_RECEIPT_APPEND")
        return receipt

    def staged(
        self,
        *,
        session_id: str,
        loop_id: str,
        parent_revision: int,
        action_sha256: str,
    ) -> WorkspaceEvidenceRegistrationReceiptV1 | None:
        path = self._registration_path(
            session_id=session_id,
            loop_id=loop_id,
            parent_revision=parent_revision,
            action_sha256=action_sha256,
        )
        if not path.exists():
            return None
        value = WorkspaceEvidenceRegistrationReceiptV1.model_validate_json(_read_regular(path))
        if (
            value.session_id != session_id
            or value.loop_id != loop_id
            or value.parent_revision != parent_revision
            or value.action_sha256 != action_sha256
        ):
            raise WorkspaceEvidenceAuthorityError("evidence registration lookup differs")
        return value

    def registration_replay(
        self,
        *,
        claim_id: str,
        schema: str,
        action_id: str,
        expected_revision: int,
        idempotency_key: str,
        acquisition_intent_id: str,
        acquisition_receipt_id: str,
        content_b64: str,
    ) -> WorkspaceEvidenceRegistrationReceiptV1 | None:
        raw = decode_canonical_content_b64(content_b64)
        intent = self.intent(acquisition_intent_id)
        acquisition = self.acquisition_receipt(acquisition_receipt_id)
        path = self._registration_path(
            session_id=intent.session_id,
            loop_id=intent.loop_id,
            parent_revision=expected_revision,
            action_sha256=intent.action_sha256,
        )
        if not path.exists():
            return None
        receipt = WorkspaceEvidenceRegistrationReceiptV1.model_validate_json(
            _read_regular(path)
        )
        if (
            schema != EVIDENCE_REGISTRATION_SCHEMA
            or intent.claim_id != claim_id
            or intent.action_id != action_id
            or intent.expected_revision != expected_revision
            or intent.idempotency_key != idempotency_key
            or acquisition.acquisition_intent_id != acquisition_intent_id
            or receipt.claim_id != claim_id
            or receipt.action_id != action_id
            or receipt.parent_revision != expected_revision
            or receipt.idempotency_key != idempotency_key
            or receipt.acquisition_intent_id != acquisition_intent_id
            or receipt.acquisition_receipt_id != acquisition_receipt_id
            or receipt.intent_receipt_sha256 != intent.receipt_sha256
            or receipt.source_acquisition_receipt_sha256
            != acquisition.receipt_sha256
            or receipt.content_sha256 != sha256(raw).hexdigest()
            or receipt.content_length != len(raw)
        ):
            self._reject(
                "registration",
                {
                    "claim_id": claim_id,
                    "action_id": action_id,
                    "expected_revision": expected_revision,
                    "acquisition_intent_id": acquisition_intent_id,
                    "acquisition_receipt_id": acquisition_receipt_id,
                },
                "evidence registration replay differs",
            )
        return receipt

    def binding_for_acquisition(
        self,
        *,
        acquisition: AcquisitionReceiptV1,
    ) -> tuple[WorkspaceSourceAcquisitionReceiptV1, bytes]:
        parts = acquisition.source_locator.split(":")
        if len(parts) != 4 or parts[0] != "loopback-source-span":
            raise WorkspaceEvidenceAuthorityError("generic acquisition locator is unsupported")
        intent_id, receipt_id, source_entry_sha256 = parts[1:]
        receipt = self.acquisition_receipt(receipt_id)
        intent = self.intent(intent_id)
        raw = _read_regular(
            self._source_path(
                claim_id=receipt.claim_id, content_sha256=receipt.content_sha256
            )
        )
        if (
            receipt.acquisition_intent_id != intent_id
            or receipt.intent_receipt_sha256 != intent.receipt_sha256
            or receipt.source_entry_sha256 != source_entry_sha256
            or receipt.content_sha256 != sha256(raw).hexdigest()
            or receipt.content_length != len(raw)
            or acquisition.sanitized_content is None
            or acquisition.sanitized_content.encode("utf-8") != raw
        ):
            raise WorkspaceEvidenceAuthorityError("generic acquisition differs from loopback receipt")
        return receipt, raw

    def execute(
        self,
        *,
        action: EvidenceAction,
        state: ClaimLoopState,
        idempotency_key: str,
        timestamp: str,
    ) -> ToolResult:
        del idempotency_key, timestamp
        stage = self.staged(
            session_id=state.session_id,
            loop_id=state.loop_id,
            parent_revision=state.revision - 1,
            action_sha256=action.action_sha256,
        )
        if stage is None:
            return ToolResult(
                status=ToolResultStatus.UNAVAILABLE,
                source_locator=f"loopback-source-span:missing:{action.action_sha256}",
                reason="server-acquired source bytes were not registered for this action",
            )
        receipt = self.acquisition_receipt(stage.acquisition_receipt_id)
        raw = _read_regular(
            self._source_path(
                claim_id=receipt.claim_id, content_sha256=receipt.content_sha256
            )
        )
        if (
            stage.claim_id != state.claim_id
            or stage.record_version != state.record_version
            or stage.parent_revision != state.revision - 1
            or stage.action_id != action.action_id
            or stage.action_sha256 != action.action_sha256
            or stage.evidence_item_id != action.evidence_item_id
            or stage.content_sha256 != sha256(raw).hexdigest()
            or stage.content_length != len(raw)
            or receipt.acquisition_intent_id != stage.acquisition_intent_id
            or receipt.receipt_sha256 != stage.source_acquisition_receipt_sha256
            or receipt.intent_receipt_sha256 != stage.intent_receipt_sha256
            or receipt.freshness_nonce != stage.freshness_nonce
        ):
            raise WorkspaceEvidenceAuthorityError("registered evidence does not bind the active action")
        try:
            content = raw.decode("utf-8", errors="strict")
        except UnicodeError as exc:
            raise WorkspaceEvidenceAuthorityError("registered source bytes are not UTF-8") from exc
        return ToolResult(
            status=ToolResultStatus.OBSERVED,
            sanitized_content=content,
            artifact_source_version=state.record_version,
            artifact_page_count=1,
            source_locator=(
                "loopback-source-span:"
                + stage.acquisition_intent_id
                + ":"
                + stage.acquisition_receipt_id
                + ":"
                + stage.source_entry_sha256
            ),
        )

    def record_proposal(self, proposal: Mapping[str, Any]) -> dict[str, Any]:
        proposal_sha256 = proposal.get("proposal_sha256")
        if not is_sha256(proposal_sha256) or proposal_sha256 != digest_value(
            {key: value for key, value in proposal.items() if key != "proposal_sha256"}
        ):
            self._reject("proposal", {}, "evidence proposal identity is invalid")
        acquisition_sha256 = proposal.get("acquisition_receipt_sha256")
        if not is_sha256(acquisition_sha256):
            self._reject(
                "proposal",
                {"proposal_sha256": proposal_sha256},
                "evidence proposal lacks its generic acquisition receipt",
            )
        path = self.proposal_root / (str(proposal_sha256) + ".json")
        self._fault("BEFORE_PROPOSAL_APPEND")
        if not _publish_new(path, canonical_json_bytes(dict(proposal))):
            if json.loads(_read_regular(path)) != dict(proposal):
                self._reject("proposal", {"proposal_sha256": proposal_sha256}, "evidence proposal collision")
        index_material = {
            "contract": "casepath.workspace-proposal-acquisition-index/1.0.0",
            "acquisition_receipt_sha256": acquisition_sha256,
            "proposal_sha256": proposal_sha256,
        }
        index = {**index_material, "receipt_sha256": digest_value(index_material)}
        index_path = self.proposal_index_root / (str(acquisition_sha256) + ".json")
        if not _publish_new(index_path, canonical_json_bytes(index)):
            if json.loads(_read_regular(index_path)) != index:
                self._reject(
                    "proposal",
                    {"acquisition_receipt_sha256": acquisition_sha256},
                    "acquisition has multiple interpretation proposals",
                )
        self._fault("AFTER_PROPOSAL_APPEND")
        return dict(proposal)

    def proposal_for_acquisition(self, acquisition_receipt_sha256: str) -> dict[str, Any]:
        index_path = self.proposal_index_root / (acquisition_receipt_sha256 + ".json")
        if not index_path.exists():
            raise WorkspaceEvidenceAuthorityError("recorded evidence proposal is absent")
        index = json.loads(_read_regular(index_path))
        index_material = {key: value for key, value in index.items() if key != "receipt_sha256"}
        if (
            index.get("contract")
            != "casepath.workspace-proposal-acquisition-index/1.0.0"
            or index.get("acquisition_receipt_sha256") != acquisition_receipt_sha256
            or index.get("receipt_sha256") != digest_value(index_material)
            or not is_sha256(index.get("proposal_sha256"))
        ):
            raise WorkspaceEvidenceAuthorityError("recorded proposal index is invalid")
        path = self.proposal_root / (str(index["proposal_sha256"]) + ".json")
        if not path.exists():
            raise WorkspaceEvidenceAuthorityError("recorded exact proposal is absent")
        proposal = json.loads(_read_regular(path))
        if (
            proposal.get("proposal_sha256") != index["proposal_sha256"]
            or proposal.get("acquisition_receipt_sha256") != acquisition_receipt_sha256
            or proposal["proposal_sha256"]
            != digest_value(
                {key: value for key, value in proposal.items() if key != "proposal_sha256"}
            )
        ):
            raise WorkspaceEvidenceAuthorityError("recorded exact proposal is invalid")
        return proposal

    def record_admission(
        self,
        *,
        capability: object,
        proposal: Mapping[str, Any],
        interpretation_sha256: str,
        authority_id: str,
        authority_source_sha256: str,
    ) -> dict[str, Any]:
        self._assert_authority_writer(
            capability=capability,
            authority_id=authority_id,
            authority_source_sha256=authority_source_sha256,
        )
        proposal_sha256 = proposal.get("proposal_sha256")
        recorded = self.proposal_for_acquisition(
            str(proposal.get("acquisition_receipt_sha256"))
        )
        if (
            recorded != dict(proposal)
            or proposal.get("interpretation_receipt_sha256")
            != interpretation_sha256
            or not is_sha256(interpretation_sha256)
        ):
            self._reject(
                "admission",
                {"proposal_sha256": proposal_sha256},
                "authority admission does not reference the exact recorded proposal",
            )
        material = {
            "contract": "casepath.workspace-evidence-authority-admission/1.0.0",
            "proposal_sha256": proposal_sha256,
            "interpretation_receipt_sha256": interpretation_sha256,
            "acquisition_receipt_sha256": proposal["acquisition_receipt_sha256"],
            "registration_receipt_sha256": proposal["registration_receipt_sha256"],
            "intent_receipt_sha256": proposal["intent_receipt_sha256"],
            "source_acquisition_receipt_sha256": proposal[
                "source_acquisition_receipt_sha256"
            ],
            "authority_id": authority_id,
            "authority_source_sha256": authority_source_sha256,
            "decision": "admitted",
            "authoritative_state_effect": "delegated_to_claim_loop_journal",
        }
        value = {**material, "receipt_sha256": digest_value(material)}
        path = self.admission_root / (value["receipt_sha256"] + ".json")
        self._claim_authority_outcome(
            acquisition_receipt_sha256=str(
                proposal["acquisition_receipt_sha256"]
            ),
            decision="admitted",
            authority_receipt_sha256=value["receipt_sha256"],
        )
        self._fault("BEFORE_ADMISSION_APPEND")
        if not _publish_new(path, canonical_json_bytes(value)):
            if json.loads(_read_regular(path)) != value:
                self._reject("admission", {"proposal_sha256": proposal_sha256}, "evidence admission collision")
        index_path = self.admission_index_root / (interpretation_sha256 + ".json")
        index_material = {
            "contract": "casepath.workspace-admission-interpretation-index/1.0.0",
            "interpretation_receipt_sha256": interpretation_sha256,
            "admission_receipt_sha256": value["receipt_sha256"],
        }
        index = {**index_material, "receipt_sha256": digest_value(index_material)}
        if not _publish_new(index_path, canonical_json_bytes(index)):
            if json.loads(_read_regular(index_path)) != index:
                self._reject(
                    "admission",
                    {"interpretation_receipt_sha256": interpretation_sha256},
                    "interpretation has multiple authority admissions",
                )
        self._fault("AFTER_ADMISSION_APPEND")
        return value

    def authority_binding(self, interpretation_receipt_sha256: str) -> dict[str, Any]:
        index_path = self.admission_index_root / (interpretation_receipt_sha256 + ".json")
        if not index_path.exists():
            raise WorkspaceEvidenceAuthorityError("authority admission index is absent")
        index = json.loads(_read_regular(index_path))
        index_material = {key: value for key, value in index.items() if key != "receipt_sha256"}
        if index.get("receipt_sha256") != digest_value(index_material):
            raise WorkspaceEvidenceAuthorityError("authority admission index is invalid")
        admission_path = self.admission_root / (str(index["admission_receipt_sha256"]) + ".json")
        if not admission_path.exists():
            raise WorkspaceEvidenceAuthorityError("authority admission receipt is absent")
        admission = json.loads(_read_regular(admission_path))
        admission_material = {
            key: value for key, value in admission.items() if key != "receipt_sha256"
        }
        expected_admission_keys = {
            "contract",
            "proposal_sha256",
            "interpretation_receipt_sha256",
            "acquisition_receipt_sha256",
            "registration_receipt_sha256",
            "intent_receipt_sha256",
            "source_acquisition_receipt_sha256",
            "authority_id",
            "authority_source_sha256",
            "decision",
            "authoritative_state_effect",
            "receipt_sha256",
        }
        if (
            set(admission) != expected_admission_keys
            or admission.get("contract")
            != "casepath.workspace-evidence-authority-admission/1.0.0"
            or admission.get("receipt_sha256")
            != index["admission_receipt_sha256"]
            or admission.get("interpretation_receipt_sha256")
            != interpretation_receipt_sha256
            or admission.get("authority_id")
            != "casepath.independent-evidence-authority/1.0.0"
            or admission.get("authority_source_sha256")
            != self._authority_source_sha256
            or admission.get("decision") != "admitted"
            or admission.get("authoritative_state_effect")
            != "delegated_to_claim_loop_journal"
            or admission.get("receipt_sha256") != digest_value(admission_material)
        ):
            raise WorkspaceEvidenceAuthorityError("authority admission receipt is invalid")
        proposal = self.proposal_for_acquisition(
            str(admission["acquisition_receipt_sha256"])
        )
        if proposal["proposal_sha256"] != admission["proposal_sha256"]:
            raise WorkspaceEvidenceAuthorityError("authority proposal/admission chain differs")
        if (
            proposal.get("interpretation_receipt_sha256")
            != interpretation_receipt_sha256
            or proposal.get("registration_receipt_sha256")
            != admission.get("registration_receipt_sha256")
            or proposal.get("intent_receipt_sha256")
            != admission.get("intent_receipt_sha256")
            or proposal.get("source_acquisition_receipt_sha256")
            != admission.get("source_acquisition_receipt_sha256")
        ):
            raise WorkspaceEvidenceAuthorityError(
                "authority admission receipt links differ from proposal"
            )
        outcome = self._authority_outcome(
            str(admission["acquisition_receipt_sha256"])
        )
        if (
            outcome.get("decision") != "admitted"
            or outcome.get("authority_receipt_sha256")
            != admission["receipt_sha256"]
        ):
            raise WorkspaceEvidenceAuthorityError(
                "authority admission is not the exclusive acquisition outcome"
            )
        binding_material = {
            "contract": "casepath.workspace-evidence-authority-binding/1.0.0",
            "proposal_sha256": proposal["proposal_sha256"],
            "admission_receipt_sha256": admission["receipt_sha256"],
            "interpretation_receipt_sha256": interpretation_receipt_sha256,
            "acquisition_receipt_sha256": admission["acquisition_receipt_sha256"],
            "registration_receipt_sha256": admission["registration_receipt_sha256"],
            "authority_id": admission["authority_id"],
            "authority_source_sha256": admission["authority_source_sha256"],
        }
        return {**binding_material, "binding_sha256": digest_value(binding_material)}


_HEALTH_POSITIVE_TERMS = (
    "cough",
    "coughing",
    "hustet",
    "husten",
    "rash",
    "ausschlag",
    "pharmacy",
    "apotheke",
    "breathing",
    "atem",
)
_HEALTH_NEGATIVE_TERMS = (
    "no health effects",
    "no immediate health risk",
    "keine gesundheitlichen folgen",
    "kein unmittelbares gesundheitsrisiko",
)
_UNCERTAINTY_TERMS = (
    "unresolved",
    "unclear",
    "unknown",
    "missing",
    "cannot safely",
    "ungeklärt",
    "unklar",
    "offen",
    "fehlt",
    "nicht sicher",
)
_INSTRUCTION_PATTERNS = (
    r"\bignore\s+(?:all\s+)?(?:previous|prior)\s+instructions?\b",
    r"\b(?:set|choose|select|override|change|mark|grant)\s+(?:the\s+)?(?:finding|readiness|parser|policy|authority|branch|normalized value)\b",
    r'(?i)["\'](?:finding|readiness|parser|policy|authority|process_branch|normalized_value)["\']\s*[:=]',
    r"\b(?:approve|deny|pay|close)\s+(?:this\s+|the\s+)?claim\b",
)
_NEGATED_HEALTH_PATTERNS = (
    r"\bno\s+(?:cough|coughing|rash|breathing problem)\b",
    r"\bwithout\s+(?:a\s+)?(?:cough|rash|breathing problem)\b",
    r"\bkein(?:e|en)?\s+(?:husten|ausschlag|atemproblem)\b",
)
_LEASE_TERMINATION_INTAKE_TERMS = (
    "termination",
    "termination notice",
    "notice of termination",
    "kündigung",
    "kündigungsschreiben",
    "mietvertragskündigung",
)
_RENT_INCREASE_INTAKE_TERMS = (
    "rent increase",
    "rent increases",
    "rent rises",
    "net rent",
    "gross rent",
    "mietzinserhöhung",
    "mietzins",
    "nettomiete",
    "bruttomiete",
)


def _term_present(text: str, term: str) -> bool:
    return re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", text) is not None


def _instruction_bearing(text: str) -> bool:
    return any(re.search(pattern, text, flags=re.IGNORECASE) is not None for pattern in _INSTRUCTION_PATTERNS)


def _substantive(text: str) -> bool:
    return len(re.findall(r"\w+", text, flags=re.UNICODE)) >= 5


def _single_edge_intake_is_decisive(process_node_id: str, text: str) -> bool:
    folded = text.casefold()
    terms = (
        _LEASE_TERMINATION_INTAKE_TERMS
        if process_node_id.endswith("lt_intake")
        else (
            _RENT_INCREASE_INTAKE_TERMS
            if process_node_id.endswith("ri_intake")
            else ()
        )
    )
    return bool(terms) and any(_term_present(folded, term) for term in terms)


class _EvidenceSemantics:
    implementation_id = "casepath.fixed-source-span-interpreter/1.0.0"
    grammar_id = "casepath.workspace-source-span-grammar/1.0.0"

    def __init__(self, adapter: LoopbackSourceByteAcquisitionAdapterV1) -> None:
        self.adapter = adapter
        self.implementation_source_sha256 = _module_sha256()

    @staticmethod
    def input_contract(*, action: EvidenceAction, state: ClaimLoopState) -> dict[str, Any]:
        template = playbook_template_from_accepted_v1(state.accepted_artifacts)
        admission = _admission(state)
        grant = admission["actor_grants"].get(action.evidence_item_id)
        fact = next((value for value in state.facts if value.get("fact_id") == action.fact_id), None)
        if not isinstance(grant, Mapping) or fact is None:
            raise ClaimLoopError("server evidence action is outside the accepted authority")
        decision_key = fact.get("decision_key")
        options = template.decision_options.get(decision_key, {}) if decision_key is not None else {}
        unresolved = template.fail_closed_normalized_values.get(decision_key) if decision_key is not None else None
        catalog = {
            "template_sha256": template.template_sha256,
            "decision_key": decision_key,
            "normalized_values": list(options),
            "unresolved_normalized_value": unresolved,
        }
        material = {
            "contract": "casepath.server-interpreted-evidence-input/1.0.0",
            "registration_schema": EVIDENCE_REGISTRATION_SCHEMA,
            "registration_body_fields": list(EVIDENCE_REGISTRATION_FIELDS),
            "adapter_id": LOOPBACK_SOURCE_BYTE_ADAPTER_ID,
            "acquisition_intent_contract": "casepath.workspace-acquisition-intent/1.0.0",
            "acquisition_receipt_contract": "casepath.workspace-source-acquisition/1.0.0",
            "registration_receipt_contract": "casepath.workspace-evidence-registration-receipt/1.0.0",
            "evidence_item_id": action.evidence_item_id,
            "fact_id": action.fact_id,
            "action_id": action.action_id,
            "expected_revision": state.revision,
            "intent_ttl_seconds": INTENT_TTL_SECONDS,
            "max_content_bytes": MAX_SOURCE_BYTES,
            "server_interpretation_only": True,
            "source_policy_sha256": admission["policy_sha256"],
            "catalog_sha256": digest_value(catalog),
            "interpreter_id": _EvidenceSemantics.implementation_id,
            "interpreter_source_sha256": _module_sha256(),
            "authority_id": "casepath.independent-evidence-authority/1.0.0",
        }
        return {**material, "input_contract_sha256": digest_value(material)}

    def source_candidate(
        self, *, action: EvidenceAction, state: ClaimLoopState
    ) -> dict[str, Any]:
        entries = [dict(value) for value in _admission(state)["source_entries"]]
        entries.sort(key=lambda value: (int(value["text_start"]), str(value["source_entry_sha256"])))
        rejected = self.adapter.rejected_source_entry_sha256s(
            claim_id=state.claim_id,
            action_id=action.action_id,
        )
        used = {
            (ref.source_sha256, ref.text_start, ref.text_end, ref.span_sha256)
            for observation in state.observations
            for ref in observation.source_refs
        }
        available = [
            value
            for value in entries
            if value["source_entry_sha256"] not in rejected
            and (value["artifact_sha256"], value["text_start"], value["text_end"], value["span_sha256"]) not in used
        ]
        if not available:
            raise ClaimLoopError("no fresh admitted source span remains for this action")
        if action.process_node_id.endswith("_intake"):
            positive = [value for value in available if any(term in value["exact_text"].casefold() for term in _HEALTH_POSITIVE_TERMS)]
            if action.process_node_id.endswith("dh_intake") and positive:
                return positive[0]
            decisive = [
                value
                for value in available
                if _substantive(value["exact_text"])
                and _single_edge_intake_is_decisive(
                    action.process_node_id, value["exact_text"]
                )
            ]
            return (decisive or available)[0]
        uncertain = [value for value in available if any(term in value["exact_text"].casefold() for term in _UNCERTAINTY_TERMS)]
        return (uncertain or available)[0]

    def _binding(
        self, *, action: EvidenceAction, state: ClaimLoopState, acquisition: AcquisitionReceiptV1
    ) -> tuple[WorkspaceSourceAcquisitionReceiptV1, dict[str, Any], str]:
        receipt, raw = self.adapter.binding_for_acquisition(acquisition=acquisition)
        text = raw.decode("utf-8", errors="strict")
        matches = [
            dict(value)
            for value in _admission(state)["source_entries"]
            if value["source_entry_sha256"] == receipt.source_entry_sha256
        ]
        if (
            len(matches) != 1
            or matches[0]["exact_text"] != text
            or matches[0]["artifact_id"] != receipt.source_artifact_id
            or matches[0]["artifact_sha256"] != receipt.source_artifact_sha256
            or matches[0]["text_start"] != receipt.text_start
            or matches[0]["text_end"] != receipt.text_end
            or receipt.action_id != action.action_id
            or receipt.action_sha256 != action.action_sha256
            or receipt.claim_id != state.claim_id
            or receipt.record_version != state.record_version
        ):
            raise ClaimLoopError("acquired source span differs from admission authority")
        return receipt, matches[0], text

    @staticmethod
    def _catalog(
        *, action: EvidenceAction, state: ClaimLoopState
    ) -> tuple[dict[str, Any], str | None, list[str], dict[str, Any]]:
        template = playbook_template_from_accepted_v1(state.accepted_artifacts)
        admission = _admission(state)
        grant = admission["actor_grants"].get(action.evidence_item_id)
        fact = next((value for value in state.facts if value.get("fact_id") == action.fact_id), None)
        if (
            fact is None
            or not isinstance(grant, Mapping)
            or set(grant)
            != {
                "contract",
                "actor_type",
                "required_process_owner",
                "authority_scope",
                "decision_bearing",
            }
            or grant.get("contract") != "casepath.workspace-actor-grant/1.0.0"
            or grant.get("actor_type") != "claim_handler"
            or not isinstance(grant.get("decision_bearing"), bool)
        ):
            raise ClaimLoopError("server evidence fact is absent")
        decision_key = fact.get("decision_key")
        options = template.decision_options.get(decision_key, {}) if decision_key is not None else {}
        unresolved = template.fail_closed_normalized_values.get(decision_key) if decision_key is not None else None
        if decision_key is not None and (not isinstance(options, Mapping) or unresolved not in options):
            raise ClaimLoopError("server evidence decision catalog is invalid")
        catalog = {
            "template_sha256": template.template_sha256,
            "decision_key": decision_key,
            "normalized_values": list(options),
            "unresolved_normalized_value": unresolved,
        }
        return catalog, unresolved, [value for value in options if value != unresolved], dict(grant)

    @staticmethod
    def _proposal_finding(
        action: EvidenceAction,
        text: str,
        unresolved: str | None,
        resolved: list[str],
        grant: Mapping[str, Any],
    ) -> str | None:
        if unresolved is None:
            raise ClaimLoopError("source span has no closed decision catalog")
        folded = text.casefold()
        if grant.get("decision_bearing") is not True:
            raise ClaimLoopError("source span lacks a decision-bearing actor grant")
        if _instruction_bearing(text):
            raise ClaimLoopError("instruction-bearing source content is not evidence")
        if not _substantive(text):
            raise ClaimLoopError("source span is not substantively interpretable")
        if len(resolved) == 1 and _single_edge_intake_is_decisive(
            action.process_node_id, text
        ):
            return resolved[0]
        if any(_term_present(folded, term) for term in _UNCERTAINTY_TERMS):
            return unresolved
        if action.process_node_id.endswith("dh_intake") and set(resolved) == {
            "dh_e01",
            "dh_e02",
        }:
            positive = any(_term_present(folded, term) for term in _HEALTH_POSITIVE_TERMS)
            negative = any(_term_present(folded, term) for term in _HEALTH_NEGATIVE_TERMS)
            negated_positive = any(
                re.search(pattern, folded, flags=re.IGNORECASE) is not None
                for pattern in _NEGATED_HEALTH_PATTERNS
            )
            if negated_positive or positive == negative:
                raise ClaimLoopError(
                    "health source span is ambiguous, negated, or contradictory"
                )
            if positive:
                return "dh_e01"
            if negative:
                return "dh_e02"
        if not action.process_node_id.endswith("_intake"):
            raise ClaimLoopError("source span is outside the intake decision grammar")
        raise ClaimLoopError("source span does not contain a decisive grammar token")

    def _interpretation(
        self,
        *,
        action: EvidenceAction,
        state: ClaimLoopState,
        acquisition: AcquisitionReceiptV1,
        receipt: WorkspaceSourceAcquisitionReceiptV1,
        entry: Mapping[str, Any],
        text: str,
        finding: str | None,
        catalog: Mapping[str, Any],
        unresolved: str | None,
    ) -> CanonicalFactInterpretationV1:
        prior_fact = next((value for value in state.facts if value.get("fact_id") == action.fact_id), None)
        if prior_fact is None:
            raise ClaimLoopError("server evidence fact is absent")
        resolved = finding is not None and finding != unresolved
        source_ref = ClaimSourceRef.model_validate(
            {
                "source_id": entry["artifact_id"],
                "source_sha256": entry["artifact_sha256"],
                "source_version": entry["source_version"],
                "locator_kind": "text_quote",
                "page": 1,
                "sanitized_excerpt": text,
                "text_start": entry["text_start"],
                "text_end": entry["text_end"],
                "field": None,
                "value": None,
                "span_sha256": entry["span_sha256"],
                "adapter_id": LOOPBACK_SOURCE_BYTE_ADAPTER_ID,
            }
        )
        observation_material = {
            "contract": "casepath.claim-observation/1.0.0",
            "observation_id": "observation."
            + digest_value(
                {
                    "acquisition_receipt_sha256": acquisition.receipt_sha256,
                    "source_entry_sha256": entry["source_entry_sha256"],
                    "action_sha256": action.action_sha256,
                }
            ),
            "fact_id": action.fact_id,
            "evidence_item_id": action.evidence_item_id,
            "value": text,
            "fact_state": "known" if resolved else "unknown",
            "normalized_value": finding if resolved and catalog["decision_key"] is not None else None,
            "explanation": (
                "A fixed-version server interpreter derived this bounded policy transition from an exact acquired source span."
                if resolved
                else "The fixed-version server interpreter abstained because this acquired source span does not resolve the current policy step."
            ),
            "evidence_status": "provided_sufficient" if resolved else "provided_insufficient",
            "source_refs": [source_ref.model_dump(mode="json")],
            "observed_at": acquisition.acquired_at,
        }
        observation = ClaimObservation.model_validate(
            {**observation_material, "observation_sha256": digest_value(observation_material)}
        )
        interpretation_payload = {
            "contract": "casepath.canonical-fact-interpretation/1.2.0",
            "action_id": action.action_id,
            "action_sha256": action.action_sha256,
            "fact_id": action.fact_id,
            "evidence_item_id": action.evidence_item_id,
            "acquisition_receipt_sha256": acquisition.receipt_sha256,
            "raw_artifact_sha256": acquisition.receipt_sha256,
            "prior_fact_sha256": digest_value(prior_fact),
            "assertion_catalog_sha256": digest_value(dict(catalog)),
            "selected_assertion_id": (
                f"server-source-span.{action.evidence_item_id}.{finding}/1" if resolved else None
            ),
            "observation": observation.model_dump(mode="json"),
            "implementation": self.implementation_id,
            "implementation_source_sha256": self.implementation_source_sha256,
            "model_calls": 0,
            "provider_calls": 0,
            "provider_credentials_read": False,
            "cost_usd": 0.0,
        }
        return CanonicalFactInterpretationV1.model_validate(
            {**interpretation_payload, "receipt_sha256": digest_value(interpretation_payload)}
        )

    def proposal(
        self, *, action: EvidenceAction, state: ClaimLoopState, acquisition: AcquisitionReceiptV1
    ) -> tuple[CanonicalFactInterpretationV1, dict[str, Any]]:
        receipt, entry, text = self._binding(action=action, state=state, acquisition=acquisition)
        registration = self.adapter.staged(
            session_id=state.session_id,
            loop_id=state.loop_id,
            parent_revision=receipt.expected_revision,
            action_sha256=action.action_sha256,
        )
        if (
            registration is None
            or registration.acquisition_receipt_id != receipt.acquisition_receipt_id
            or registration.source_acquisition_receipt_sha256 != receipt.receipt_sha256
        ):
            raise ClaimLoopError("server evidence registration binding is absent")
        catalog, unresolved, resolved, grant = self._catalog(action=action, state=state)
        finding = self._proposal_finding(action, text, unresolved, resolved, grant)
        interpretation = self._interpretation(
            action=action,
            state=state,
            acquisition=acquisition,
            receipt=receipt,
            entry=entry,
            text=text,
            finding=finding,
            catalog=catalog,
            unresolved=unresolved,
        )
        proposal_material = {
            "contract": "casepath.workspace-server-interpretation-proposal/1.0.0",
            "authoritative": False,
            "claim_id": state.claim_id,
            "loop_id": state.loop_id,
            "record_version": state.record_version,
            "parent_revision": receipt.expected_revision,
            "action_id": action.action_id,
            "action_sha256": action.action_sha256,
            "acquisition_intent_id": receipt.acquisition_intent_id,
            "acquisition_receipt_id": receipt.acquisition_receipt_id,
            "acquisition_receipt_sha256": acquisition.receipt_sha256,
            "registration_receipt_sha256": registration.receipt_sha256,
            "content_sha256": receipt.content_sha256,
            "content_length": receipt.content_length,
            "source_entry_sha256": entry["source_entry_sha256"],
            "source_artifact_sha256": entry["artifact_sha256"],
            "text_start": entry["text_start"],
            "text_end": entry["text_end"],
            "byte_start": entry["byte_start"],
            "byte_end": entry["byte_end"],
            "span_sha256": entry["span_sha256"],
            "interpreter_id": self.implementation_id,
            "interpreter_source_sha256": self.implementation_source_sha256,
            "grammar_id": self.grammar_id,
                "grammar_sha256": digest_value(
                    {
                        "positive": list(_HEALTH_POSITIVE_TERMS),
                        "negative": list(_HEALTH_NEGATIVE_TERMS),
                        "uncertainty": list(_UNCERTAINTY_TERMS),
                        "lease_termination_intake": list(
                            _LEASE_TERMINATION_INTAKE_TERMS
                        ),
                        "rent_increase_intake": list(
                            _RENT_INCREASE_INTAKE_TERMS
                        ),
                    }
                ),
            "schema_id": INTERPRETATION_SCHEMA_ID,
            "schema_sha256": INTERPRETATION_SCHEMA_SHA256,
            "catalog_sha256": digest_value(catalog),
            "policy_sha256": _admission(state)["policy_sha256"],
            "actor_grant_sha256": digest_value(grant),
            "intent_receipt_sha256": receipt.intent_receipt_sha256,
            "source_acquisition_receipt_sha256": receipt.receipt_sha256,
            "freshness_nonce": receipt.freshness_nonce,
            "proposed_normalized_value": finding if finding != unresolved else None,
            "proposed_fact_state": interpretation.observation.fact_state,
            "proposed_evidence_status": interpretation.observation.evidence_status,
            "interpretation_receipt_sha256": interpretation.receipt_sha256,
        }
        proposal = {**proposal_material, "proposal_sha256": digest_value(proposal_material)}
        return interpretation, proposal

class WorkspaceEvidenceProposalInterpreterV1:
    def __init__(self, semantics: _EvidenceSemantics) -> None:
        self.semantics = semantics

    def interpret(
        self, *, action: EvidenceAction, state: ClaimLoopState, acquisition: AcquisitionReceiptV1
    ) -> CanonicalFactInterpretationV1:
        interpretation, proposal = self.semantics.proposal(
            action=action, state=state, acquisition=acquisition
        )
        self.semantics.adapter.record_proposal(proposal)
        return interpretation


class ServerInterpretedWorkspaceEvidenceV1:
    """Facade exposing a non-authoritative proposer and a separate authority."""

    implementation_id = _EvidenceSemantics.implementation_id

    def __init__(self, adapter: LoopbackSourceByteAcquisitionAdapterV1) -> None:
        self.adapter = adapter
        self.semantics = _EvidenceSemantics(adapter)
        self.proposal_interpreter = WorkspaceEvidenceProposalInterpreterV1(self.semantics)
        self.authority = IndependentWorkspaceEvidenceAuthorityV1(
            adapter,
            interpreter_source_sha256=self.semantics.implementation_source_sha256,
        )

    @property
    def implementation_source_sha256(self) -> str:
        return self.semantics.implementation_source_sha256

    def input_contract(self, *, action: EvidenceAction, state: ClaimLoopState) -> dict[str, Any]:
        return self.semantics.input_contract(action=action, state=state)

    def source_candidate(self, *, action: EvidenceAction, state: ClaimLoopState) -> dict[str, Any]:
        return self.semantics.source_candidate(action=action, state=state)

    def record_registration_envelope_rejection(
        self,
        *,
        claim_id: str,
        request_sha256: str,
        reason: str,
    ) -> None:
        self.adapter._record_rejection(
            "registration-envelope",
            {
                "claim_id": claim_id,
                "request_sha256": request_sha256,
            },
            reason,
        )

    def interpret(
        self, *, action: EvidenceAction, state: ClaimLoopState, acquisition: AcquisitionReceiptV1
    ) -> CanonicalFactInterpretationV1:
        return self.proposal_interpreter.interpret(
            action=action, state=state, acquisition=acquisition
        )

    def validate_interpretation_authority(
        self,
        *,
        action: EvidenceAction,
        state: ClaimLoopState,
        acquisition: AcquisitionReceiptV1,
        interpretation: CanonicalFactInterpretationV1,
    ) -> None:
        self.authority.validate(
            action=action,
            state=state,
            acquisition=acquisition,
            interpretation=interpretation,
        )

    def validate_interpreted_source_binding(
        self,
        *,
        action: EvidenceAction,
        state: ClaimLoopState,
        acquisition: AcquisitionReceiptV1,
        observation: ClaimObservation,
    ) -> None:
        receipt, raw = self.adapter.binding_for_acquisition(acquisition=acquisition)
        matches = [
            value
            for value in _admission(state)["source_entries"]
            if value["source_entry_sha256"] == receipt.source_entry_sha256
        ]
        source = observation.source_refs[0] if len(observation.source_refs) == 1 else None
        if (
            len(matches) != 1
            or source is None
            or observation.value.encode("utf-8") != raw
            or source.source_id != receipt.source_artifact_id
            or source.source_sha256 != receipt.source_artifact_sha256
            or source.text_start != receipt.text_start
            or source.text_end != receipt.text_end
            or source.span_sha256 != receipt.content_sha256
            or source.sanitized_excerpt != observation.value
            or action.action_id != receipt.action_id
            or state.claim_id != receipt.claim_id
        ):
            raise ClaimLoopError("independent authority rejected the observation source binding")

    def authority_binding_for_interpretation(
        self, interpretation: CanonicalFactInterpretationV1
    ) -> dict[str, Any]:
        return self.adapter.authority_binding(interpretation.receipt_sha256)

    def record_interpretation_rejection(
        self,
        *,
        action: EvidenceAction,
        state: ClaimLoopState,
        acquisition: AcquisitionReceiptV1,
        reason: str,
    ) -> dict[str, Any]:
        return self.authority.record_rejection(
            action=action,
            state=state,
            acquisition=acquisition,
            reason=reason,
        )

    def authority_rejection_for_acquisition(
        self, acquisition_receipt_sha256: str
    ) -> dict[str, Any]:
        return self.adapter.authority_rejection(acquisition_receipt_sha256)

    def validate_recorded_authority_rejection(
        self,
        *,
        action: EvidenceAction,
        state: ClaimLoopState,
        acquisition: AcquisitionReceiptV1,
        rejection_receipt: Mapping[str, Any],
    ) -> None:
        recorded = self.adapter.authority_rejection(acquisition.receipt_sha256)
        if (
            recorded != dict(rejection_receipt)
            or recorded.get("session_id") != state.session_id
            or recorded.get("loop_id") != state.loop_id
            or recorded.get("claim_id") != state.claim_id
            or recorded.get("record_version") != state.record_version
            or recorded.get("parent_revision") != state.revision
            or recorded.get("parent_state_sha256") != state.state_sha256
            or recorded.get("action_id") != action.action_id
            or recorded.get("action_sha256") != action.action_sha256
            or recorded.get("dispatch_sha256") != state.active_dispatch_sha256
            or recorded.get("acquisition_receipt_sha256")
            != acquisition.receipt_sha256
        ):
            raise ClaimLoopError(
                "workspace journal rejection differs from its authority receipt"
            )

    def validate_recorded_authority_event(self, event: Any) -> None:
        if event.event_type not in {
            "OBSERVATION_INGESTED",
            "EVIDENCE_PROPOSAL_REJECTED",
        }:
            return
        if event.event_type == "EVIDENCE_PROPOSAL_REJECTED":
            recorded = self.adapter.authority_rejection(
                str(event.command.get("acquisition_receipt_sha256"))
            )
            if event.command.get("authority_rejection_receipt") != recorded:
                raise ClaimLoopError("workspace journal rejection chain differs")
            return
        artifact = event.command.get("tool_artifact_receipt")
        if not isinstance(artifact, Mapping):
            raise ClaimLoopError("workspace authority artifact is absent")
        if (
            event.session_id == "casepath-workspace-claim-loop-v1"
            and artifact.get("adapter_id") != self.adapter.adapter_id
        ):
            raise ClaimLoopError("workspace authority adapter identity changed")
        if artifact.get("adapter_id") != self.adapter.adapter_id:
            return
        interpretation = artifact.get("interpretation")
        if not isinstance(interpretation, Mapping):
            raise ClaimLoopError("workspace authority interpretation is absent")
        expected = self.adapter.authority_binding(
            str(interpretation.get("receipt_sha256"))
        )
        if event.command.get("evidence_authority_binding") != expected:
            raise ClaimLoopError("workspace journal authority chain differs")

    def validate_observation_source_binding(
        self,
        *,
        action: EvidenceAction,
        state: ClaimLoopState,
        acquisition: AcquisitionReceiptV1,
        receipt: Any,
    ) -> None:
        self.validate_interpreted_source_binding(
            action=action,
            state=state,
            acquisition=acquisition,
            observation=receipt.observation,
        )


__all__ = [
    "EVIDENCE_REGISTRATION_FIELDS",
    "EVIDENCE_REGISTRATION_SCHEMA",
    "IndependentWorkspaceEvidenceAuthorityV1",
    "LOOPBACK_SOURCE_BYTE_ADAPTER_ID",
    "LoopbackSourceByteAcquisitionAdapterV1",
    "ServerInterpretedWorkspaceEvidenceV1",
    "WorkspaceAcquisitionIntentV1",
    "WorkspaceEvidenceAuthorityError",
    "WorkspaceEvidenceRegistrationReceiptV1",
    "WorkspaceEvidenceProposalInterpreterV1",
    "WorkspaceSourceAcquisitionReceiptV1",
    "decode_canonical_content_b64",
]
