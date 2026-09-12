from __future__ import annotations

import json
import os
import stat
import tempfile
import time
import unicodedata
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from threading import RLock
from typing import Any, Literal

from pydantic import model_validator

from .claim_loop import (
    ClaimLoopError,
    CorrectionToolResult,
    ToolResult,
    adapter_implementation_sha256_v1,
    playbook_template_from_accepted_v1,
    project_claim_loop_artifacts_v1,
)
from .claim_loop import (
    StructuredMouldArtifactInterpreterV2 as _StructuredTypedArtifactInterpreter,
)
from .claim_loop_contracts import (
    AcquisitionReceiptV1,
    CanonicalFactInterpretationV1,
    ClaimObservation,
    ClaimSourceRef,
    ClaimLoopState,
    CorrectionArtifactReceipt,
    CorrectionEffect,
    EvidenceAction,
    ProjectionLedgerEntry,
    SixAgentCycleReceipt,
    ScopedCorrection,
    ToolArtifactReceipt,
    ToolResultStatus,
)
from .claim_loop_service import ClaimLoopService, ClaimLoopServiceError
from .claim_loop_store import ClaimLoopStoreError
from .claim_workspace_intake_v1 import (
    IntakeCompilationError,
    validate_recorded_intake_assessment,
)
from .claim_workspace_v1 import ClaimWorkspaceError, ClaimWorkspaceService
from .foundation.common import canonical_json_bytes, digest_text, digest_value, is_sha256
from .foundation.contracts import FoundationModel
from .multi_agent import DeterministicStructuredAgent, NemotronMultiAgentOrchestrator
from .pipeline_v15 import ClaimPipeline
from .playbook_template import PlaybookTemplate
from .workspace_corpus import PublicCorpus
from .workspace_operational_projection_v1 import (
    WorkspaceOperationalProjectionError,
    derive_workspace_operational_projection_v1,
)
from .workspace_evidence_authority_v1 import (
    LOOPBACK_SOURCE_BYTE_ADAPTER_ID,
    LoopbackSourceByteAcquisitionAdapterV1,
    ServerInterpretedWorkspaceEvidenceV1,
    WorkspaceEvidenceAuthorityError,
)

WORKSPACE_EVIDENCE_ADAPTER_ID = LOOPBACK_SOURCE_BYTE_ADAPTER_ID
WORKSPACE_CORRECTION_ADAPTER_ID = (
    "casepath.correction.workspace-evidence-withdrawal/1.0.0"
)
WORKSPACE_CLAIM_LOOP_SESSION_ID = "casepath-workspace-claim-loop-v1"
WORKSPACE_TYPED_EVIDENCE_FILENAME = "casepath-evidence.json"
WORKSPACE_TYPED_EVIDENCE_MEDIA_TYPE = (
    "application/vnd.casepath.typed-evidence+json"
)
WORKSPACE_QUEUE_STABLE_READ_ATTEMPTS = 64
WORKSPACE_QUEUE_STABLE_READ_INTERVAL_SECONDS = 0.025


class WorkspaceClaimLoopError(ValueError):
    def __init__(
        self,
        message: str,
        *,
        conflict_envelope: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.conflict_envelope = (
            dict(conflict_envelope) if conflict_envelope is not None else None
        )


class WorkspaceEvidenceStageReceiptV1(FoundationModel):
    contract: Literal["casepath.workspace-evidence-stage/1.0.0"] = (
        "casepath.workspace-evidence-stage/1.0.0"
    )
    session_id: str
    loop_id: str
    claim_id: str
    record_version: str
    parent_revision: int
    parent_state_sha256: str
    action_id: str
    action_sha256: str
    evidence_item_id: str
    idempotency_key: str
    content: str
    content_sha256: str
    staged_at: str
    receipt_sha256: str

    @model_validator(mode="after")
    def validate_receipt(self) -> WorkspaceEvidenceStageReceiptV1:
        if (
            not self.session_id
            or not self.loop_id
            or not self.claim_id
            or not self.record_version
            or isinstance(self.parent_revision, bool)
            or self.parent_revision < 1
            or not self.action_id
            or not self.evidence_item_id
            or not 8 <= len(self.idempotency_key) <= 128
            or not is_sha256(self.action_sha256)
            or not is_sha256(self.parent_state_sha256)
            or not is_sha256(self.content_sha256)
            or not is_sha256(self.receipt_sha256)
            or self.content_sha256 != sha256(self.content.encode("utf-8")).hexdigest()
        ):
            raise ValueError("workspace evidence stage identity is invalid")
        try:
            parsed = datetime.fromisoformat(self.staged_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("workspace evidence stage timestamp is invalid") from exc
        if parsed.tzinfo is None:
            raise ValueError("workspace evidence stage timestamp lacks a timezone")
        payload = self.model_dump(mode="json", exclude={"receipt_sha256"})
        if digest_value(payload) != self.receipt_sha256:
            raise ValueError("workspace evidence stage self-hash differs")
        return self


class WorkspaceEvidenceStageReceiptV2(FoundationModel):
    """Immutable admission receipt for exact browser-created evidence bytes."""

    contract: Literal["casepath.workspace-evidence-stage/2.0.0"] = (
        "casepath.workspace-evidence-stage/2.0.0"
    )
    session_id: str
    loop_id: str
    claim_id: str
    record_version: str
    parent_revision: int
    parent_state_sha256: str
    action_id: str
    action_sha256: str
    evidence_item_id: str
    idempotency_key: str
    filename: Literal["casepath-evidence.json"]
    media_type: Literal["application/vnd.casepath.typed-evidence+json"]
    content: str
    claimed_content_sha256: str
    content_sha256: str
    staged_at: str
    receipt_sha256: str

    @model_validator(mode="after")
    def validate_receipt(self) -> WorkspaceEvidenceStageReceiptV2:
        actual_content_sha256 = sha256(self.content.encode("utf-8")).hexdigest()
        if (
            not self.session_id
            or not self.loop_id
            or not self.claim_id
            or not self.record_version
            or isinstance(self.parent_revision, bool)
            or self.parent_revision < 1
            or not self.action_id
            or not self.evidence_item_id
            or not 8 <= len(self.idempotency_key) <= 128
            or not is_sha256(self.action_sha256)
            or not is_sha256(self.parent_state_sha256)
            or not is_sha256(self.claimed_content_sha256)
            or not is_sha256(self.content_sha256)
            or not is_sha256(self.receipt_sha256)
            or self.claimed_content_sha256 != actual_content_sha256
            or self.content_sha256 != actual_content_sha256
        ):
            raise ValueError("workspace evidence stage v2 identity is invalid")
        try:
            parsed = datetime.fromisoformat(self.staged_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("workspace evidence stage timestamp is invalid") from exc
        if parsed.tzinfo is None:
            raise ValueError("workspace evidence stage timestamp lacks a timezone")
        payload = self.model_dump(mode="json", exclude={"receipt_sha256"})
        if digest_value(payload) != self.receipt_sha256:
            raise ValueError("workspace evidence stage v2 self-hash differs")
        return self


def _source_sha256() -> str:
    return sha256(Path(__file__).read_bytes()).hexdigest()


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _ensure_directory_durable(path: Path) -> None:
    """Create each missing directory and publish it durably to its parent."""

    missing: list[Path] = []
    cursor = path
    while not cursor.exists():
        missing.append(cursor)
        if cursor.parent == cursor:
            raise WorkspaceClaimLoopError("workspace evidence root is unavailable")
        cursor = cursor.parent
    if cursor.is_symlink() or not cursor.is_dir():
        raise WorkspaceClaimLoopError("workspace evidence parent is invalid")
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
            raise WorkspaceClaimLoopError("workspace stage is not a regular file")
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
    path.parent.mkdir(parents=True, exist_ok=True)
    _fsync_directory(path.parent)
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


class WorkspaceBrowserEvidenceAdapterV1:
    """Persistent provider-free adapter for one browser-staged evidence action."""

    adapter_id = WORKSPACE_EVIDENCE_ADAPTER_ID
    implementation_id = "casepath.workspace-browser-evidence/2.0.0"

    def __init__(
        self,
        root: str | Path,
        *,
        interpreter: _StructuredTypedArtifactInterpreter | None = None,
    ) -> None:
        self.root = Path(root).resolve()
        self.stage_root = self.root / "stages-v2"
        self.interpreter = interpreter or _StructuredTypedArtifactInterpreter()
        _ensure_directory_durable(self.stage_root)
        if self.stage_root.is_symlink() or not self.stage_root.is_dir():
            raise WorkspaceClaimLoopError("workspace evidence root is invalid")
        _fsync_directory(self.stage_root)
        self._implementation_source_sha256 = _source_sha256()

    @property
    def implementation_source_sha256(self) -> str:
        if _source_sha256() != self._implementation_source_sha256:
            raise WorkspaceClaimLoopError("workspace evidence adapter source changed")
        return self._implementation_source_sha256

    @property
    def implementation_sha256(self) -> str:
        return adapter_implementation_sha256_v1(
            adapter_id=self.adapter_id,
            implementation_id=self.implementation_id,
            implementation_source_sha256=self.implementation_source_sha256,
        )

    @staticmethod
    def _stage_identity(
        *,
        session_id: str,
        loop_id: str,
        parent_revision: int,
        action_sha256: str,
    ) -> str:
        return digest_value(
            {
                "contract": "casepath.workspace-evidence-stage-resource/2.0.0",
                "session_id": session_id,
                "loop_id": loop_id,
                "parent_revision": parent_revision,
                "action_sha256": action_sha256,
            }
        )

    def _path(
        self,
        *,
        session_id: str,
        loop_id: str,
        parent_revision: int,
        action_sha256: str,
    ) -> Path:
        return self.stage_root / (
            self._stage_identity(
                session_id=session_id,
                loop_id=loop_id,
                parent_revision=parent_revision,
                action_sha256=action_sha256,
            )
            + ".json"
        )

    def stage(
        self,
        *,
        state: ClaimLoopState,
        action: EvidenceAction,
        filename: str,
        media_type: str,
        content: str,
        claimed_content_sha256: str,
        idempotency_key: str,
        staged_at: str,
    ) -> WorkspaceEvidenceStageReceiptV2:
        if (
            state.selected_action is None
            or state.selected_action != action
            or state.active_dispatch_sha256 is not None
        ):
            raise WorkspaceClaimLoopError(
                "workspace evidence is not bound to an idle selected action"
            )
        try:
            if filename != WORKSPACE_TYPED_EVIDENCE_FILENAME:
                raise WorkspaceClaimLoopError("workspace evidence filename is unsupported")
            if media_type != WORKSPACE_TYPED_EVIDENCE_MEDIA_TYPE:
                raise WorkspaceClaimLoopError("workspace evidence media type is unsupported")
            if sha256(content.encode("utf-8")).hexdigest() != claimed_content_sha256:
                raise WorkspaceClaimLoopError("workspace evidence content hash differs")
            self.interpreter.validate_content(
                action=action,
                state=state,
                content=content,
            )
        except ClaimLoopError as exc:
            raise WorkspaceClaimLoopError(str(exc)) from exc
        path = self._path(
            session_id=state.session_id,
            loop_id=state.loop_id,
            parent_revision=state.revision,
            action_sha256=action.action_sha256,
        )
        if path.exists():
            existing = WorkspaceEvidenceStageReceiptV2.model_validate_json(
                _read_regular(path)
            )
            stable_request = {
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
                "filename": filename,
                "media_type": media_type,
                "content": content,
                "claimed_content_sha256": claimed_content_sha256,
                "content_sha256": sha256(content.encode("utf-8")).hexdigest(),
            }
            if any(
                getattr(existing, key) != value for key, value in stable_request.items()
            ):
                raise WorkspaceClaimLoopError(
                    "workspace evidence action was staged with different input"
                )
            return existing
        payload = {
            "contract": "casepath.workspace-evidence-stage/2.0.0",
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
            "filename": filename,
            "media_type": media_type,
            "content": content,
            "claimed_content_sha256": claimed_content_sha256,
            "content_sha256": sha256(content.encode("utf-8")).hexdigest(),
            "staged_at": staged_at,
        }
        receipt = WorkspaceEvidenceStageReceiptV2.model_validate(
            {**payload, "receipt_sha256": digest_value(payload)}
        )
        raw = canonical_json_bytes(receipt.model_dump(mode="json"))
        if not _publish_new(path, raw):
            existing = WorkspaceEvidenceStageReceiptV2.model_validate_json(
                _read_regular(path)
            )
            stable_fields = (
                "session_id",
                "loop_id",
                "claim_id",
                "record_version",
                "parent_revision",
                "parent_state_sha256",
                "action_id",
                "action_sha256",
                "evidence_item_id",
                "idempotency_key",
                "filename",
                "media_type",
                "content",
                "claimed_content_sha256",
                "content_sha256",
            )
            if any(
                getattr(existing, key) != getattr(receipt, key) for key in stable_fields
            ):
                raise WorkspaceClaimLoopError(
                    "workspace evidence action was staged with different input"
                )
            return existing
        return receipt

    def staged(
        self,
        *,
        session_id: str,
        loop_id: str,
        parent_revision: int,
        action_sha256: str,
    ) -> WorkspaceEvidenceStageReceiptV2 | None:
        path = self._path(
            session_id=session_id,
            loop_id=loop_id,
            parent_revision=parent_revision,
            action_sha256=action_sha256,
        )
        if not path.exists():
            return None
        try:
            receipt = WorkspaceEvidenceStageReceiptV2.model_validate_json(
                _read_regular(path)
            )
        except (OSError, TypeError, ValueError) as exc:
            raise WorkspaceClaimLoopError(
                "workspace evidence stage is invalid"
            ) from exc
        if (
            receipt.session_id != session_id
            or receipt.loop_id != loop_id
            or receipt.parent_revision != parent_revision
            or receipt.action_sha256 != action_sha256
        ):
            raise WorkspaceClaimLoopError(
                "workspace evidence stage lookup identity is invalid"
            )
        return receipt

    def execute(
        self,
        *,
        action: EvidenceAction,
        state: ClaimLoopState,
        idempotency_key: str,
        timestamp: str,
    ) -> ToolResult:
        del idempotency_key, timestamp
        receipt = self.staged(
            session_id=state.session_id,
            loop_id=state.loop_id,
            parent_revision=state.revision - 1,
            action_sha256=action.action_sha256,
        )
        if receipt is None:
            return ToolResult(
                status=ToolResultStatus.UNAVAILABLE,
                source_locator=f"workspace-stage:missing:{action.action_sha256}",
                reason="browser evidence was not staged for this action",
            )
        if (
            receipt.session_id != state.session_id
            or receipt.loop_id != state.loop_id
            or receipt.claim_id != state.claim_id
            or receipt.record_version != state.record_version
            or receipt.parent_revision != state.revision - 1
            or receipt.action_id != action.action_id
            or receipt.action_sha256 != action.action_sha256
            or receipt.evidence_item_id != action.evidence_item_id
        ):
            raise WorkspaceClaimLoopError(
                "workspace evidence stage does not bind the active action"
            )
        try:
            self.interpreter.validate_content(
                action=action,
                state=state,
                content=receipt.content,
            )
        except ClaimLoopError as exc:
            raise WorkspaceClaimLoopError(str(exc)) from exc
        return ToolResult(
            status=ToolResultStatus.OBSERVED,
            sanitized_content=receipt.content,
            artifact_source_version=state.record_version,
            artifact_page_count=1,
            source_locator=f"workspace-stage:{receipt.receipt_sha256}",
        )


class WorkspaceEvidenceWithdrawalCorrectionAdapterV1:
    """Withdraw one exact admitted assertion without minting a replacement truth."""

    adapter_id = WORKSPACE_CORRECTION_ADAPTER_ID

    def execute(
        self,
        *,
        source_artifact: ToolArtifactReceipt,
        state: ClaimLoopState,
        timestamp: str,
    ) -> CorrectionToolResult:
        observation = source_artifact.observation
        ledger_matches = tuple(
            entry
            for entry in state.projection_ledger
            if entry.kind == "observation"
            and entry.record_sha256 == observation.observation_sha256
            and entry.artifact_receipt_sha256 == source_artifact.receipt_sha256
        )
        history_matches = tuple(
            entry
            for entry in state.action_history
            if entry.action.action_id == source_artifact.action_id
            and entry.action.action_sha256 == source_artifact.action_sha256
            and entry.outcome == "observed"
            and entry.observation_sha256 == observation.observation_sha256
        )
        fact = next(
            (
                value
                for value in state.facts
                if value.get("fact_id") == observation.fact_id
            ),
            None,
        )
        evidence = next(
            (
                value
                for value in state.checklist.get("items", [])
                if value.get("item_id") == observation.evidence_item_id
            ),
            None,
        )
        if (
            state.active_dispatch_sha256 is not None
            or source_artifact.adapter_id != WORKSPACE_EVIDENCE_ADAPTER_ID
            or source_artifact.session_id != state.session_id
            or source_artifact.loop_id != state.loop_id
            or source_artifact.artifact_source_version != state.record_version
            or len(ledger_matches) != 1
            or len(history_matches) != 1
            or observation.fact_state != "known"
            or observation.evidence_status != "provided_sufficient"
            or len(observation.source_refs) != 1
            or observation.source_refs[0].adapter_id
            != WORKSPACE_EVIDENCE_ADAPTER_ID
            or fact is None
            or evidence is None
            or fact.get("state") != "known"
            or fact.get("value") != observation.value
            or fact.get("normalized_value") != observation.normalized_value
            or fact.get("explanation") != observation.explanation
            or evidence.get("status") != "provided_sufficient"
            or evidence.get("fact_id") != observation.fact_id
            or any(
                correction.effect.fact_id == observation.fact_id
                and correction.effect.evidence_item_id
                == observation.evidence_item_id
                for correction in state.corrections
            )
        ):
            raise ClaimLoopError(
                "workspace correction source is not one current sufficient assertion"
            )
        effect = CorrectionEffect(
            fact_id=observation.fact_id,
            evidence_item_id=observation.evidence_item_id,
            value="Correction receipt: the admitted evidence is not decision-sufficient.",
            fact_state="unknown",
            normalized_value=None,
            explanation=(
                "A case-local deterministic correction withdraws only this exact "
                "evidence assertion; it supplies no replacement fact."
            ),
            evidence_status="provided_insufficient",
        )
        return CorrectionToolResult(
            effect=effect,
            issuer_id=self.adapter_id,
            provenance_note=(
                "Server-derived withdrawal of one admitted workspace assertion at "
                f"{timestamp}; provider-free and case-local."
            ),
        )


class WorkspaceStructuredEvidenceInterpreterV1(_StructuredTypedArtifactInterpreter):
    """Admit one handler classification of an exact, pre-existing source span.

    Browser bytes are a proposal only.  The accepted observable package owns
    the source registry, actor grant, closed finding catalog, and sufficiency
    decision.  The resulting observation cites the original message-body
    projection rather than this typed proposal.
    """

    implementation_id = "casepath.workspace-source-attestation-interpreter/2.0.0"
    schema = "casepath.workspace-source-attestation/2.0.0"
    document_kind = "handler_source_classification"
    attestation = "handler_attested_source_classification_v1"
    _DOCUMENT_KEYS = frozenset(
        {
            "schema",
            "document_kind",
            "evidence_item_id",
            "source_entry_sha256",
            "finding",
            "attestation",
            "operator_note",
        }
    )

    @property
    def implementation_source_sha256(self) -> str:
        return _source_sha256()

    @classmethod
    def _parse_document(cls, content: str) -> dict[str, str]:
        if content != unicodedata.normalize("NFC", content):
            raise ClaimLoopError("workspace source classification must use Unicode NFC")
        if len(content.encode("utf-8")) > 100_000:
            raise ClaimLoopError("workspace source classification exceeds the byte limit")
        try:
            value = json.loads(
                content,
                object_pairs_hook=cls._duplicate_rejecting_object,
            )
        except (json.JSONDecodeError, RecursionError, UnicodeError) as exc:
            raise ClaimLoopError(
                "workspace source classification is not valid JSON"
            ) from exc
        if not isinstance(value, dict) or set(value) != cls._DOCUMENT_KEYS:
            raise ClaimLoopError("workspace source classification fields are not closed")
        if any(not isinstance(item, str) for item in value.values()):
            raise ClaimLoopError("workspace source classification fields must be strings")
        if (
            value["schema"] != cls.schema
            or value["document_kind"] != cls.document_kind
        ):
            raise ClaimLoopError("workspace source classification schema is unsupported")
        if any(item != unicodedata.normalize("NFC", item) for item in value.values()):
            raise ClaimLoopError("workspace source values must use Unicode NFC")
        if value["attestation"] != cls.attestation:
            raise ClaimLoopError("workspace source classification lacks attestation")
        if not is_sha256(value["source_entry_sha256"]):
            raise ClaimLoopError("workspace source entry identity is invalid")
        if len(value["operator_note"]) > 1_000:
            raise ClaimLoopError("workspace operator note is oversized")
        return value

    @staticmethod
    def _admission(state: ClaimLoopState) -> dict[str, Any]:
        package = state.accepted_artifacts.get("observable_package")
        admission = (
            package.get("workspace_evidence_admission")
            if isinstance(package, Mapping)
            else None
        )
        if not isinstance(admission, Mapping):
            raise ClaimLoopError("workspace source admission policy is absent")
        material = dict(admission)
        policy_sha256 = material.pop("policy_sha256", None)
        entries = admission.get("source_entries")
        grants = admission.get("actor_grants")
        if (
            admission.get("contract")
            != "casepath.workspace-evidence-admission-policy/1.0.0"
            or policy_sha256 != digest_value(material)
            or not isinstance(entries, list)
            or not entries
            or not isinstance(grants, Mapping)
        ):
            raise ClaimLoopError("workspace source admission policy is invalid")
        seen: set[str] = set()
        for entry in entries:
            if not isinstance(entry, Mapping):
                raise ClaimLoopError("workspace source entry is invalid")
            entry_material = dict(entry)
            entry_sha256 = entry_material.pop("source_entry_sha256", None)
            if (
                not is_sha256(entry_sha256)
                or entry_sha256 != digest_value(entry_material)
                or entry_sha256 in seen
                or entry.get("source_kind") != "observable_message_span"
                or entry.get("support_scope") != "case_specific"
                or entry.get("locator_kind") != "text_span"
                or entry.get("page") != 1
                or not isinstance(entry.get("exact_text"), str)
                or not entry.get("exact_text")
                or digest_text(str(entry["exact_text"]))
                != entry.get("span_sha256")
            ):
                raise ClaimLoopError("workspace source entry identity is invalid")
            seen.add(entry_sha256)
        return dict(admission)

    @classmethod
    def input_contract(
        cls,
        *,
        action: EvidenceAction,
        state: ClaimLoopState,
    ) -> dict[str, Any]:
        inherited = super().input_contract(action=action, state=state)
        admission = cls._admission(state)
        grant = admission["actor_grants"].get(action.evidence_item_id)
        if not isinstance(grant, Mapping):
            raise ClaimLoopError("workspace evidence action lacks an actor grant")
        material = {
            **{
                key: value
                for key, value in inherited.items()
                if key != "input_contract_sha256"
            },
            "schema": cls.schema,
            "document_kind": cls.document_kind,
            "attestation": cls.attestation,
            "operator_note_max_characters": 1_000,
            "source_entries": admission["source_entries"],
            "source_registry_file_sha256": admission[
                "source_registry_file_sha256"
            ],
            "admission_policy_sha256": admission["policy_sha256"],
            "actor_grant": dict(grant),
        }
        return {**material, "input_contract_sha256": digest_value(material)}

    @classmethod
    def validate_content(
        cls,
        *,
        action: EvidenceAction,
        state: ClaimLoopState,
        content: str,
    ) -> dict[str, str]:
        document = cls._parse_document(content)
        contract = cls.input_contract(action=action, state=state)
        if document["evidence_item_id"] != action.evidence_item_id:
            raise ClaimLoopError("workspace source classification targets another item")
        if document["finding"] not in contract["finding_values"]:
            raise ClaimLoopError("workspace source finding is outside the catalog")
        if not any(
            entry["source_entry_sha256"] == document["source_entry_sha256"]
            for entry in contract["source_entries"]
        ):
            raise ClaimLoopError("workspace source entry is not admitted")
        if (
            document["finding"] != contract["unresolved_finding"]
            and contract["actor_grant"].get("decision_bearing") is not True
        ):
            raise ClaimLoopError(
                "handler attestation cannot resolve this specialist obligation"
            )
        return document

    @classmethod
    def _source_entry(
        cls,
        *,
        action: EvidenceAction,
        state: ClaimLoopState,
        document: Mapping[str, str],
    ) -> dict[str, Any]:
        contract = cls.input_contract(action=action, state=state)
        matches = [
            dict(entry)
            for entry in contract["source_entries"]
            if entry["source_entry_sha256"] == document["source_entry_sha256"]
        ]
        if len(matches) != 1:
            raise ClaimLoopError("workspace source entry is ambiguous")
        return matches[0]

    def interpret(
        self,
        *,
        action: EvidenceAction,
        state: ClaimLoopState,
        acquisition: AcquisitionReceiptV1,
    ) -> CanonicalFactInterpretationV1:
        content = acquisition.sanitized_content
        if (
            acquisition.status is not ToolResultStatus.OBSERVED
            or content is None
            or acquisition.artifact_page_count != 1
            or acquisition.record_version != state.record_version
            or acquisition.action_id != action.action_id
        ):
            raise ClaimLoopError("workspace source acquisition boundary is invalid")
        document = self.validate_content(action=action, state=state, content=content)
        contract = self.input_contract(action=action, state=state)
        entry = self._source_entry(action=action, state=state, document=document)
        prior_fact = next(
            (value for value in state.facts if value.get("fact_id") == action.fact_id),
            None,
        )
        if prior_fact is None:
            raise ClaimLoopError("workspace source fact is absent")
        resolved = document["finding"] != contract["unresolved_finding"]
        source_ref = ClaimSourceRef.model_validate(
            {
                "source_id": entry["artifact_id"],
                "source_sha256": entry["artifact_sha256"],
                "source_version": entry["source_version"],
                "locator_kind": "text_quote",
                "page": entry["page"],
                "sanitized_excerpt": entry["exact_text"],
                "text_start": entry["text_start"],
                "text_end": entry["text_end"],
                "field": None,
                "value": None,
                "span_sha256": entry["span_sha256"],
                "adapter_id": acquisition.adapter_id,
            }
        )
        explanation = (
            "A handler classified an exact admitted source span; this is "
            "source-linked but not independently verified."
            if resolved
            else "The exact admitted source span leaves this policy step unresolved."
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
            "value": entry["exact_text"],
            "fact_state": "known" if resolved else "unknown",
            "normalized_value": (
                document["finding"]
                if resolved and contract["decision_key"] is not None
                else None
            ),
            "explanation": explanation,
            "evidence_status": (
                "provided_sufficient" if resolved else "provided_insufficient"
            ),
            "source_refs": [source_ref.model_dump(mode="json")],
            "observed_at": acquisition.acquired_at,
        }
        observation = ClaimObservation.model_validate(
            {
                **observation_material,
                "observation_sha256": digest_value(observation_material),
            }
        )
        catalog = {
            "input_contract_sha256": contract["input_contract_sha256"],
            "admission_policy_sha256": contract["admission_policy_sha256"],
            "source_entry_sha256": entry["source_entry_sha256"],
            "document_schema": sorted(self._DOCUMENT_KEYS),
        }
        payload = {
            "contract": "casepath.canonical-fact-interpretation/1.2.0",
            "action_id": action.action_id,
            "action_sha256": action.action_sha256,
            "fact_id": action.fact_id,
            "evidence_item_id": action.evidence_item_id,
            "acquisition_receipt_sha256": acquisition.receipt_sha256,
            "raw_artifact_sha256": acquisition.receipt_sha256,
            "prior_fact_sha256": digest_value(prior_fact),
            "assertion_catalog_sha256": digest_value(catalog),
            "selected_assertion_id": (
                f"workspace-attestation.{action.evidence_item_id}."
                f"{document['finding']}/2"
                if resolved
                else None
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
            {**payload, "receipt_sha256": digest_value(payload)}
        )

    def validate_observation_source_binding(
        self,
        *,
        action: EvidenceAction,
        state: ClaimLoopState,
        acquisition: AcquisitionReceiptV1,
        receipt: ToolArtifactReceipt,
    ) -> None:
        """Re-open the accepted registry authority at the storage boundary."""

        self.validate_interpreted_source_binding(
            action=action,
            state=state,
            acquisition=acquisition,
            observation=receipt.observation,
        )

    def validate_interpreted_source_binding(
        self,
        *,
        action: EvidenceAction,
        state: ClaimLoopState,
        acquisition: AcquisitionReceiptV1,
        observation: ClaimObservation,
    ) -> None:
        """Validate the exact admitted source before a tool receipt is built."""

        document = self.validate_content(
            action=action,
            state=state,
            content=acquisition.sanitized_content or "",
        )
        entry = self._source_entry(action=action, state=state, document=document)
        source = observation.source_refs[0]
        expected = {
            "source_id": entry["artifact_id"],
            "source_sha256": entry["artifact_sha256"],
            "source_version": entry["source_version"],
            "locator_kind": "text_quote",
            "page": entry["page"],
            "sanitized_excerpt": entry["exact_text"],
            "text_start": entry["text_start"],
            "text_end": entry["text_end"],
            "field": None,
            "value": None,
            "span_sha256": entry["span_sha256"],
            "adapter_id": acquisition.adapter_id,
        }
        if (
            source.model_dump(mode="json")
            != ClaimSourceRef.model_validate(expected).model_dump(mode="json")
            or observation.value != entry["exact_text"]
        ):
            raise ClaimLoopError("workspace observation source binding is invalid")


class DeterministicTemplateCyclePipelineRouter:
    """Resolve the existing six-role graph against the loop's accepted template."""

    def __init__(self, storage: Any, default_pipeline: ClaimPipeline) -> None:
        self.storage = storage
        self.__storage_capability = storage._issue_owned_session_write_capability(
            WORKSPACE_CLAIM_LOOP_SESSION_ID
        )
        self.default_pipeline = default_pipeline
        self.playbook_template = default_pipeline.playbook_template
        self._pipelines: dict[str, ClaimPipeline] = {
            self.playbook_template.template_sha256: default_pipeline
        }
        self._lock = RLock()

    def for_template(self, template: PlaybookTemplate) -> ClaimPipeline:
        with self._lock:
            pipeline = self._pipelines.get(template.template_sha256)
            if pipeline is None:
                pipeline = ClaimPipeline(
                    self.storage,
                    model_mode=self.default_pipeline.model_mode,
                    agent_orchestrator=NemotronMultiAgentOrchestrator(
                        self.storage,
                        agent_runner=DeterministicStructuredAgent(),
                        playbook_template=template,
                    ),
                    playbook_template=template,
                    pace_seconds=0,
                )
                self._pipelines[template.template_sha256] = pipeline
            return pipeline

    def _source_write_scope(self) -> Any:
        return self.storage._owned_session_write_scope(
            WORKSPACE_CLAIM_LOOP_SESSION_ID,
            self.__storage_capability,
        )

    def analyze_cycle(self, **kwargs: Any) -> dict[str, Any]:
        return self.default_pipeline.analyze_cycle(**kwargs)

    def create(self, *args: Any, **kwargs: Any) -> str:
        return self.default_pipeline.create(*args, **kwargs)


@dataclass(frozen=True, slots=True)
class WorkspacePlaybookBundleV1:
    template: PlaybookTemplate
    observable_package: dict[str, Any]
    legal_context: dict[str, Any]
    finding_labels: dict[str, str]
    receipt: dict[str, Any]


class WorkspaceClaimLoopServiceV1:
    """Claim-stable facade over the existing authoritative ClaimLoop journal."""

    def __init__(
        self,
        *,
        workspace: ClaimWorkspaceService,
        claim_loop: ClaimLoopService,
        pipeline_router: DeterministicTemplateCyclePipelineRouter,
        adapter: LoopbackSourceByteAcquisitionAdapterV1,
        interpreter: ServerInterpretedWorkspaceEvidenceV1,
        correction_adapter: WorkspaceEvidenceWithdrawalCorrectionAdapterV1,
        native_claim_loop: ClaimLoopService | None = None,
    ) -> None:
        self.workspace = workspace
        self.claim_loop = claim_loop
        self.pipeline_router = pipeline_router
        self.adapter = adapter
        self.interpreter = interpreter
        self.correction_adapter = correction_adapter
        self.native_claim_loop = native_claim_loop
        self._operational_projection_lock = RLock()
        self._operational_projection_cache: dict[
            tuple[str, str | None, str | None], bytes
        ] = {}
        self._operational_roster_cache: tuple[
            tuple[int, int, int, int, int],
            str,
            list[dict[str, Any]],
            dict[str, dict[str, Any]],
        ] | None = None
        if (
            self.interpreter.adapter is not self.adapter
            or self.interpreter.proposal_interpreter is self.interpreter.authority
        ):
            raise WorkspaceClaimLoopError(
                "workspace acquisition, proposal, and authority boundaries are not distinct"
            )
        if self.claim_loop.correction_adapters.get(correction_adapter.adapter_id) is not (
            correction_adapter
        ):
            raise WorkspaceClaimLoopError(
                "workspace correction authority is not configured exactly"
            )

    @staticmethod
    def _create_key(assessment_sha256: str) -> str:
        if not is_sha256(assessment_sha256):
            raise WorkspaceClaimLoopError("workspace assessment identity is invalid")
        return "workspace-loop." + assessment_sha256

    @classmethod
    def _loop_id(cls, assessment_sha256: str) -> str:
        return "loop." + digest_value(
            {
                "contract": "casepath.claim-loop-create-resource/1.0.0",
                "session_id": WORKSPACE_CLAIM_LOOP_SESSION_ID,
                "idempotency_key": cls._create_key(assessment_sha256),
            }
        )

    def _authority_store_for_loop(self, loop_id: str) -> Any:
        """Select authority from the immutable creation prefix only.

        Revision one contains the accepted source package and no acquired
        evidence sidecars.  Reading only that prefix avoids interpreting a
        native journal through the ordinary workspace authority before its
        recorded native binding can be inspected.
        """

        try:
            initial_state = self.claim_loop.store.state_at_revision(
                session_id=WORKSPACE_CLAIM_LOOP_SESSION_ID,
                loop_id=loop_id,
                revision=1,
            )
        except ClaimLoopStoreError as exc:
            raise WorkspaceClaimLoopError(str(exc)) from exc
        if self._native_proposal_binding(initial_state) is None:
            return self.claim_loop.store
        if self.native_claim_loop is None:
            raise WorkspaceClaimLoopError(
                "native workspace ClaimLoop authority is unavailable"
            )
        return self.native_claim_loop.store

    def _validate_authority_sidecars(self, loop_ids: tuple[str, ...]) -> None:
        """Validate each loop with the authority recorded at loop creation."""

        existing_loop_ids = set(
            self.claim_loop.store.loop_ids_read_only(
                session_id=WORKSPACE_CLAIM_LOOP_SESSION_ID
            )
        )
        grouped: dict[int, tuple[Any, list[str]]] = {}
        for loop_id in dict.fromkeys(loop_ids):
            if loop_id not in existing_loop_ids:
                continue
            store = self._authority_store_for_loop(loop_id)
            grouped.setdefault(id(store), (store, []))[1].append(loop_id)
        for store, selected_loop_ids in grouped.values():
            store.validate_authority_sidecars_read_only(
                session_id=WORKSPACE_CLAIM_LOOP_SESSION_ID,
                loop_ids=tuple(selected_loop_ids),
            )

    @staticmethod
    def _validated_native_proposed_action(value: Any) -> dict[str, Any] | None:
        if value is None:
            return None
        if not isinstance(value, Mapping) or set(value) != {
            "audience",
            "enabled",
            "requested_contents",
        }:
            raise WorkspaceClaimLoopError("native proposed action fields are invalid")
        audience = value.get("audience")
        enabled = value.get("enabled")
        contents = value.get("requested_contents")
        if audience not in {"internal", "provider", "claimant", "authority"} or not isinstance(enabled, bool):
            raise WorkspaceClaimLoopError("native proposed action routing is invalid")
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
            raise WorkspaceClaimLoopError("native proposed action contents are invalid")
        return {
            "audience": audience,
            "enabled": enabled,
            "requested_contents": list(contents),
        }

    def _native_current_proposed_action(
        self,
        state: ClaimLoopState | None,
        events: tuple[Any, ...],
    ) -> dict[str, Any] | None:
        """Read the latest fallible action for the active native inquiry.

        The action is presentation-only.  Journal state, sufficiency, and the
        server-selected evidence action continue to come from ClaimLoop.
        """

        if (
            state is None
            or self._native_proposal_binding(state) is None
            or state.selected_action is None
        ):
            return None
        fact_id = state.selected_action.fact_id
        package = state.accepted_artifacts.get("observable_package")
        roster = package.get("native_need_roster") if isinstance(package, Mapping) else []
        matches = [row for row in roster if row.get("fact_id") == fact_id]
        if len(matches) != 1:
            raise WorkspaceClaimLoopError("native active inquiry binding is invalid")
        if state.native_proposal_revisions:
            latest = state.native_proposal_revisions[-1]
            disposition = next(
                (
                    value
                    for value in latest.action_dispositions
                    if value.prior_fact_id == fact_id
                ),
                None,
            )
            if disposition is None:
                raise WorkspaceClaimLoopError(
                    "latest native revision omits the active action lifecycle"
                )
            if disposition.disposition == "retired":
                return None
            action = next(
                (
                    value
                    for value in latest.actions
                    if value.action_id == disposition.replacement_action_id
                ),
                None,
            )
            if action is None:
                raise WorkspaceClaimLoopError(
                    "latest native revision action lineage is invalid"
                )
            return self._validated_native_proposed_action(
                {
                    "audience": action.audience,
                    "enabled": True,
                    "requested_contents": list(action.requested_contents),
                }
            )
        current = self._validated_native_proposed_action(
            matches[0].get("proposed_action")
        )
        for event in events:
            command = event.command
            if event.event_type == "OBSERVATION_INGESTED":
                observation = command.get("observation")
                if not isinstance(observation, Mapping) or observation.get("fact_id") != fact_id:
                    continue
                artifact = command.get("tool_artifact_receipt")
                content = artifact.get("sanitized_content") if isinstance(artifact, Mapping) else None
                try:
                    packet = json.loads(content) if isinstance(content, str) else None
                except (json.JSONDecodeError, UnicodeError) as exc:
                    raise WorkspaceClaimLoopError(
                        "native observation action packet is invalid"
                    ) from exc
                if isinstance(packet, Mapping) and "proposed_action" in packet:
                    current = self._validated_native_proposed_action(
                        packet.get("proposed_action")
                    )
            elif event.event_type == "CORRECTION_APPLIED":
                correction = command.get("correction")
                effect = correction.get("effect") if isinstance(correction, Mapping) else None
                if not isinstance(effect, Mapping) or effect.get("fact_id") != fact_id:
                    continue
                context = command.get("client_request_context")
                fields = context.get("result_fields") if isinstance(context, Mapping) else None
                if isinstance(fields, Mapping) and "proposed_action" in fields:
                    current = self._validated_native_proposed_action(
                        fields.get("proposed_action")
                    )
        return current

    def _scoped_operational_projection(
        self,
        projection: Mapping[str, Any],
        loop_state: ClaimLoopState | None,
        loop_events: tuple[Any, ...] = (),
    ) -> dict[str, Any]:
        """Bind readiness copy to the authority that produced the loop plan."""

        material = {
            key: deepcopy(value)
            for key, value in projection.items()
            if key != "projection_sha256"
        }
        native_plan = (
            loop_state is not None
            and self._native_proposal_binding(loop_state) is not None
        )
        material["readiness_scope"] = (
            "provisional_plan" if native_plan else "claim_process"
        )
        material["provisional_next_action"] = (
            self._native_current_proposed_action(loop_state, loop_events)
            if native_plan
            else None
        )
        next_state = material.get("next_state")
        if (
            native_plan
            and isinstance(next_state, dict)
            and next_state.get("kind") == "decision_ready"
        ):
            next_state["title"] = "Review provisional-plan coverage"
            material["principal_blocker"] = (
                "No unresolved inquiry remains in the admitted provisional plan"
            )
        proposed = material["provisional_next_action"]
        if (
            native_plan
            and isinstance(next_state, dict)
            and isinstance(proposed, Mapping)
            and proposed.get("enabled") is True
        ):
            contents = proposed["requested_contents"]
            audience = (
                "internal review" if proposed["audience"] == "internal" else proposed["audience"]
            )
            remainder = len(contents) - 1
            suffix = f" (+{remainder} more)" if remainder else ""
            next_state["title"] = (
                f"Proposed next step ({audience}): {contents[0]}{suffix}"
            )
        return {**material, "projection_sha256": digest_value(material)}

    def _operational_projections(
        self,
        workspace_states: list[dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        expected_by_claim: dict[str, str] = {}
        for workspace_state in workspace_states:
            assessment = workspace_state.get("intake_assessment")
            if isinstance(assessment, Mapping):
                assessment_sha256 = assessment.get("assessment_sha256")
                if not is_sha256(assessment_sha256):
                    raise WorkspaceClaimLoopError(
                        "workspace assessment identity is invalid"
                    )
                expected_by_claim[workspace_state["claim_id"]] = self._loop_id(
                    assessment_sha256
                )
        try:
            existing_loop_ids = set(
                self.claim_loop.store.loop_ids_read_only(
                    session_id=WORKSPACE_CLAIM_LOOP_SESSION_ID
                )
            )
            grouped: dict[int, tuple[Any, list[str]]] = {}
            store_by_loop: dict[str, Any] = {}
            for loop_id in dict.fromkeys(expected_by_claim.values()):
                if loop_id not in existing_loop_ids:
                    continue
                store = self._authority_store_for_loop(loop_id)
                store_by_loop[loop_id] = store
                key = id(store)
                grouped.setdefault(key, (store, []))[1].append(loop_id)
            snapshots: dict[str, tuple[bytes, dict[str, Any], str]] = {}
            for store, loop_ids in grouped.values():
                snapshots.update(
                    store.state_bytes_prefixes_read_only(
                        session_id=WORKSPACE_CLAIM_LOOP_SESSION_ID,
                        loop_ids=tuple(loop_ids),
                    )
                )
        except ClaimLoopStoreError as exc:
            raise WorkspaceClaimLoopError(str(exc)) from exc
        projections: dict[str, dict[str, Any]] = {}
        for workspace_state in workspace_states:
            claim_id = workspace_state["claim_id"]
            expected_loop_id = expected_by_claim.get(claim_id)
            snapshot = (
                snapshots.get(expected_loop_id)
                if expected_loop_id is not None
                else None
            )
            cache_key = (
                str(workspace_state["state_sha256"]),
                snapshot[2] if snapshot is not None else None,
                str(snapshot[1]["last_event_sha256"]) if snapshot is not None else None,
            )
            with self._operational_projection_lock:
                cached = self._operational_projection_cache.get(cache_key)
            if cached is not None:
                projections[claim_id] = json.loads(cached)
                continue
            loop_state = (
                ClaimLoopState.model_validate_json(snapshot[0])
                if snapshot is not None
                else None
            )
            loop_events = (
                store_by_loop[expected_loop_id].events(
                    session_id=WORKSPACE_CLAIM_LOOP_SESSION_ID,
                    loop_id=expected_loop_id,
                )
                if snapshot is not None and expected_loop_id is not None
                else ()
            )
            try:
                projection = self._scoped_operational_projection(
                    derive_workspace_operational_projection_v1(
                        workspace_state=workspace_state,
                        loop_state=loop_state,
                        loop_journal_prefix=(
                            snapshot[1] if snapshot is not None else None
                        ),
                        expected_loop_id=expected_loop_id,
                    ),
                    loop_state,
                    loop_events,
                )
            except WorkspaceOperationalProjectionError as exc:
                raise WorkspaceClaimLoopError(str(exc)) from exc
            projection_bytes = canonical_json_bytes(projection)
            with self._operational_projection_lock:
                self._operational_projection_cache[cache_key] = projection_bytes
                # The workspace is deliberately finite (150 claims), but keep
                # a bounded safety margin for stale revisions during fault tests.
                if len(self._operational_projection_cache) > 1_024:
                    self._operational_projection_cache.pop(
                        next(iter(self._operational_projection_cache))
                    )
            projections[claim_id] = json.loads(projection_bytes)
        return projections

    def _authority_loop_ids(
        self,
        workspace_states: list[dict[str, Any]],
    ) -> tuple[str, ...]:
        loop_ids: list[str] = []
        for workspace_state in workspace_states:
            assessment = workspace_state.get("intake_assessment")
            if assessment is None:
                continue
            if (
                not isinstance(assessment, Mapping)
                or not is_sha256(assessment.get("assessment_sha256"))
            ):
                raise WorkspaceClaimLoopError(
                    "workspace assessment identity is invalid"
                )
            loop_ids.append(self._loop_id(str(assessment["assessment_sha256"])))
        if len(loop_ids) != len(set(loop_ids)):
            raise WorkspaceClaimLoopError("workspace claim-loop roster is duplicated")
        return tuple(loop_ids)

    def detail(self, claim_id: str) -> dict[str, Any]:
        """Return workspace detail only after its ClaimLoop sidecars validate."""

        try:
            detail = self.workspace.detail(claim_id)
            state = detail.get("state")
            if not isinstance(state, dict):
                raise WorkspaceClaimLoopError("workspace detail state is invalid")
            loop_ids = self._authority_loop_ids([state])
            existing_loop_ids = set(
                self.claim_loop.store.loop_ids_read_only(
                    session_id=WORKSPACE_CLAIM_LOOP_SESSION_ID
                )
            )
            for loop_id in loop_ids:
                if loop_id in existing_loop_ids:
                    self._validate_authority_sidecars((loop_id,))
            return detail
        except ClaimWorkspaceError as exc:
            raise WorkspaceClaimLoopError(str(exc)) from exc
        except ClaimLoopStoreError as exc:
            raise WorkspaceClaimLoopError(str(exc)) from exc

    def queue(self, **kwargs: Any) -> dict[str, Any]:
        """Project the queue from one read-only cut of both journals."""

        for attempt in range(WORKSPACE_QUEUE_STABLE_READ_ATTEMPTS):
            version_before = self.claim_loop.store.journal_version_token()
            with self._operational_projection_lock:
                roster_cache = self._operational_roster_cache
            if roster_cache is not None and roster_cache[0] == version_before:
                # A database-stable cache still depends on the admitted corpus.
                # Scan the closed inventory before trusting it; a file edit does
                # not change SQLite's data-version token.
                corpus_before = self.workspace.corpus.runtime_identity_token()
                if roster_cache[1] != corpus_before:
                    raise WorkspaceClaimLoopError(
                        "operational queue corpus identity differs"
                    )
                workspace_states = roster_cache[2]
                projections = roster_cache[3]
                cache_miss = False
            else:
                workspace_states = self.workspace.states()
                corpus_before = self.workspace.corpus.admitted_runtime_identity_token
                projections = self._operational_projections(workspace_states)
                cache_miss = True
            version_captured = self.claim_loop.store.journal_version_token()
            if version_captured != version_before:
                if attempt + 1 < WORKSPACE_QUEUE_STABLE_READ_ATTEMPTS:
                    time.sleep(WORKSPACE_QUEUE_STABLE_READ_INTERVAL_SECONDS)
                continue
            if cache_miss:
                with self._operational_projection_lock:
                    self._operational_roster_cache = (
                        version_captured,
                        corpus_before,
                        workspace_states,
                        projections,
                    )
            try:
                result = self.workspace.queue(
                    operational_projections=projections,
                    _states_snapshot=workspace_states,
                    _validated_operational_snapshot=True,
                    **kwargs,
                )
            except ClaimWorkspaceError as exc:
                raise WorkspaceClaimLoopError(str(exc)) from exc
            try:
                self._validate_authority_sidecars(
                    self._authority_loop_ids(workspace_states)
                )
            except ClaimLoopStoreError as exc:
                raise WorkspaceClaimLoopError(str(exc)) from exc
            # Recheck both authorities after response construction.  A caller
            # never receives a projection straddling a journal commit or a
            # corpus path/content replacement.
            corpus_after = self.workspace.corpus.runtime_identity_token()
            version_after = self.claim_loop.store.journal_version_token()
            if version_after == version_before and corpus_after == corpus_before:
                return result
            if attempt + 1 < WORKSPACE_QUEUE_STABLE_READ_ATTEMPTS:
                time.sleep(WORKSPACE_QUEUE_STABLE_READ_INTERVAL_SECONDS)
        else:
            raise WorkspaceClaimLoopError(
                "workspace journals changed continuously during queue projection"
            )

    def rebuild(self, *, timestamp: str | None = None) -> dict[str, Any]:
        """Reconstruct and bind the complete longitudinal queue projection."""

        timestamp = timestamp or datetime.now(timezone.utc).isoformat()
        expected_claim_ids = tuple(sorted(self.workspace.corpus.bindings))
        try:
            workspace_snapshot = self.workspace.states()
        except ClaimWorkspaceError as exc:
            raise WorkspaceClaimLoopError(str(exc)) from exc
        workspace_by_claim = {
            str(value["claim_id"]): value for value in workspace_snapshot
        }
        if (
            len(workspace_by_claim) != len(workspace_snapshot)
            or tuple(sorted(workspace_by_claim)) != expected_claim_ids
        ):
            raise WorkspaceClaimLoopError(
                "operational rebuild workspace roster differs from the corpus"
            )
        expected_loop_ids: list[str] = []
        for claim_id in expected_claim_ids:
            state = workspace_by_claim[claim_id]
            if state.get("binding") != self.workspace.corpus.binding(claim_id):
                raise WorkspaceClaimLoopError(
                    "operational rebuild workspace binding differs from the corpus"
                )
            assessment = state.get("intake_assessment")
            if assessment is not None:
                if (
                    not isinstance(assessment, Mapping)
                    or not is_sha256(assessment.get("assessment_sha256"))
                ):
                    raise WorkspaceClaimLoopError(
                        "operational rebuild assessment identity is invalid"
                    )
                expected_loop_ids.append(
                    self._loop_id(str(assessment["assessment_sha256"]))
                )
        try:
            actual_loop_ids = self.claim_loop.store.loop_ids_read_only(
                session_id=WORKSPACE_CLAIM_LOOP_SESSION_ID
            )
        except ClaimLoopStoreError as exc:
            raise WorkspaceClaimLoopError(str(exc)) from exc
        if not set(actual_loop_ids).issubset(expected_loop_ids):
            raise WorkspaceClaimLoopError(
                "operational rebuild claim-loop roster differs from the workspace"
            )
        # Rebuild is an authority recovery operation, not a cache read.  Drop
        # every process-local derived value so validated journal bytes are the
        # sole input even if an earlier cache object was corrupted in memory.
        with self._operational_projection_lock:
            self._operational_roster_cache = None
            self._operational_projection_cache.clear()
        # A fixed-time queue call performs the same journal/version checks used
        # by the product route and populates the validated roster cache.
        self.queue(now=timestamp, limit=1)
        with self._operational_projection_lock:
            cached = self._operational_roster_cache
        if cached is None:
            raise WorkspaceClaimLoopError("operational rebuild captured no roster")
        workspace_states = cached[2]
        projections = cached[3]
        if (
            tuple(sorted(value["claim_id"] for value in workspace_states))
            != expected_claim_ids
            or set(projections) != set(expected_claim_ids)
        ):
            raise WorkspaceClaimLoopError(
                "operational rebuild captured an incomplete corpus roster"
            )
        workspace_roster = [
            {
                "claim_id": value["claim_id"],
                "revision": value["revision"],
                "state_sha256": value["state_sha256"],
                "last_event_sha256": value["last_event_sha256"],
            }
            for value in workspace_states
        ]
        loop_roster = [
            {
                "claim_id": claim_id,
                "claim_loop_prefix": projections[claim_id]["claim_loop_prefix"],
            }
            for claim_id in sorted(projections)
        ]
        projection_roster = [
            {
                "claim_id": claim_id,
                "projection_sha256": projections[claim_id]["projection_sha256"],
            }
            for claim_id in sorted(projections)
        ]
        workspace_sha256 = digest_value(workspace_roster)
        loop_sha256 = digest_value(loop_roster)
        projection_sha256 = digest_value(projection_roster)
        expected_claim_roster_sha256 = digest_value(list(expected_claim_ids))
        semantic = {
            "corpus_identity": self.workspace.corpus.identity,
            "expected_claim_count": len(expected_claim_ids),
            "expected_claim_roster_sha256": expected_claim_roster_sha256,
            "workspace_state_roster_sha256": workspace_sha256,
            "claim_loop_prefix_roster_sha256": loop_sha256,
            "operational_projection_roster_sha256": projection_sha256,
        }
        material = {
            "contract": "casepath.workspace-operational-rebuild/1.0.0",
            "claim_count": len(workspace_roster),
            **semantic,
            "queue_semantic_sha256": digest_value(semantic),
            "authority": "workspace_and_claim_loop_events",
            "timestamp": timestamp,
        }
        return {**material, "receipt_sha256": digest_value(material)}

    def _workspace_state(
        self,
        claim_id: str,
        *,
        expected_revision: int | None = None,
        expected_state_sha256: str | None = None,
    ) -> dict[str, Any]:
        try:
            state = self.workspace.store.recover(claim_id)
        except ClaimWorkspaceError as exc:
            raise WorkspaceClaimLoopError(str(exc)) from exc
        if state.get("workflow_state") != "in_review" or not isinstance(
            state.get("intake_assessment"), Mapping
        ):
            raise WorkspaceClaimLoopError(
                "deterministic workspace intake must be accepted first"
            )
        if expected_revision is not None and state["revision"] != expected_revision:
            raise WorkspaceClaimLoopError("workspace claim revision changed")
        if (
            expected_state_sha256 is not None
            and state["state_sha256"] != expected_state_sha256
        ):
            raise WorkspaceClaimLoopError("workspace claim state changed")
        return state

    def _bundle(self, state: Mapping[str, Any]) -> WorkspacePlaybookBundleV1:
        return build_workspace_playbook_v1(
            corpus=self.workspace.corpus,
            claim_id=str(state["claim_id"]),
            assessment=state["intake_assessment"],
        )

    def native_binding(self, claim_id: str) -> dict[str, Any]:
        """Bind a native proposal to the one workspace ClaimLoop identity."""

        state = self._workspace_state(claim_id)
        assessment_sha256 = str(state["intake_assessment"]["assessment_sha256"])
        bundle = self._bundle(state)
        material = {
            "contract": "casepath.workspace-native-loop-binding/1.0.0",
            "claim_id": claim_id,
            "workspace_revision": state["revision"],
            "workspace_state_sha256": state["state_sha256"],
            "assessment_sha256": assessment_sha256,
            "loop_id": self._loop_id(assessment_sha256),
            "create_idempotency_key": self._create_key(assessment_sha256),
            "workspace_binding": deepcopy(
                bundle.observable_package["workspace_binding"]
            ),
        }
        return {**material, "binding_receipt_sha256": digest_value(material)}

    @staticmethod
    def _native_proposal_binding(state: ClaimLoopState) -> dict[str, Any] | None:
        package = state.accepted_artifacts.get("observable_package")
        receipt = (
            package.get("native_proposal_receipt")
            if isinstance(package, Mapping)
            else None
        )
        if receipt is None:
            return None
        if (
            not isinstance(receipt, Mapping)
            or receipt.get("authority") != "fallible_proposal_only"
            or not isinstance(receipt.get("cycle_id"), str)
            or not is_sha256(receipt.get("proposal_sha256"))
            or not is_sha256(receipt.get("source_prefix_sha256"))
        ):
            raise WorkspaceClaimLoopError("native proposal provenance is invalid")
        return deepcopy(dict(receipt))

    def _bundle_from_loop(
        self, workspace_state: Mapping[str, Any], state: ClaimLoopState
    ) -> WorkspacePlaybookBundleV1:
        if self._native_proposal_binding(state) is None:
            return self._bundle(workspace_state)
        accepted = state.accepted_artifacts
        template = playbook_template_from_accepted_v1(accepted)
        package = accepted.get("observable_package")
        legal = accepted.get("legal_research")
        if not isinstance(package, Mapping) or not isinstance(legal, Mapping):
            raise WorkspaceClaimLoopError("native accepted artifacts are incomplete")
        receipt_material = {
            "contract": "casepath.workspace-native-playbook-compilation/1.0.0",
            "claim_id": state.claim_id,
            "template_sha256": template.template_sha256,
            "observable_package_sha256": digest_value(dict(package)),
            "legal_context_sha256": digest_value(dict(legal)),
            "authority": "accepted_claim_loop_artifacts",
        }
        return WorkspacePlaybookBundleV1(
            template=template,
            observable_package=deepcopy(dict(package)),
            legal_context=deepcopy(dict(legal)),
            finding_labels={},
            receipt={
                **receipt_material,
                "receipt_sha256": digest_value(receipt_material),
            },
        )

    def ensure(
        self,
        claim_id: str,
        *,
        expected_workspace_revision: int,
        expected_workspace_state_sha256: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        try:
            workspace_state = self.workspace.store.state_at_revision(
                claim_id, expected_workspace_revision
            )
        except ClaimWorkspaceError as exc:
            raise WorkspaceClaimLoopError(str(exc)) from exc
        if (
            workspace_state.get("state_sha256")
            != expected_workspace_state_sha256
            or workspace_state.get("workflow_state") != "in_review"
            or not isinstance(workspace_state.get("intake_assessment"), Mapping)
        ):
            raise WorkspaceClaimLoopError(
                "workspace ensure prefix is not an accepted intake"
            )
        bundle = self._bundle(workspace_state)
        loop_id = self._loop_id(
            str(workspace_state["intake_assessment"]["assessment_sha256"])
        )
        request = {
            "claim_id": claim_id,
            "expected_workspace_revision": expected_workspace_revision,
            "expected_workspace_state_sha256": expected_workspace_state_sha256,
        }
        try:
            existing = self.claim_loop.store.lookup_client_request(
                session_id=WORKSPACE_CLAIM_LOOP_SESSION_ID,
                loop_id=loop_id,
                idempotency_key=idempotency_key,
                request_type="workspace_ensure",
                request=request,
            )
        except ClaimLoopStoreError as exc:
            raise WorkspaceClaimLoopError(
                str(exc)
            ) from exc
        if existing is not None:
            if existing.get("failure") is not None:
                raise WorkspaceClaimLoopError(
                    str(existing["failure"]["detail"]),
                    conflict_envelope=existing["failure"],
                )
            if existing.get("response") is not None:
                return dict(existing["response"])
            binding = {
                **existing,
                "request_sha256": digest_value(request),
            }
        else:
            # A fresh command must still own the current workspace CAS.  Only
            # an already-reserved/completed request may replay an older prefix.
            self._workspace_state(
                claim_id,
                expected_revision=expected_workspace_revision,
                expected_state_sha256=expected_workspace_state_sha256,
            )
            try:
                binding = self.claim_loop._bind_client_request(
                    session_id=WORKSPACE_CLAIM_LOOP_SESSION_ID,
                    loop_id=loop_id,
                    idempotency_key=idempotency_key,
                    request_type="workspace_ensure",
                    request=request,
                )
            except ClaimLoopServiceError as exc:
                raise WorkspaceClaimLoopError(
                    str(exc), conflict_envelope=exc.conflict_envelope
                ) from exc
        pipeline = self.pipeline_router.for_template(bundle.template)
        select_idempotency_key = (
            "workspace-select.initial."
            + str(workspace_state["intake_assessment"]["assessment_sha256"])[:24]
        )
        try:
            with self.pipeline_router._source_write_scope():
                source_run_id = pipeline.create_declarative_source(
                    claim_id,
                    observable_package=bundle.observable_package,
                    legal_research=bundle.legal_context,
                    session_id=WORKSPACE_CLAIM_LOOP_SESSION_ID,
                )
            created = self.claim_loop.create(
                session_id=WORKSPACE_CLAIM_LOOP_SESSION_ID,
                source_run_id=source_run_id,
                idempotency_key=self._create_key(
                    str(workspace_state["intake_assessment"]["assessment_sha256"])
                ),
            )
            self.claim_loop.select_action(
                session_id=WORKSPACE_CLAIM_LOOP_SESSION_ID,
                loop_id=str(created["loop_id"]),
                idempotency_key=select_idempotency_key,
            )
        except (ClaimLoopServiceError, KeyError, TypeError, ValueError) as exc:
            raise WorkspaceClaimLoopError(str(exc)) from exc
        # The public ensure request owns one exact loop prefix.  If the loop
        # existed when the request was reserved, the request-store snapshot is
        # its result.  Otherwise this request created the loop and owns the
        # immutable initial-selection event.  Either branch survives a crash
        # without migrating to a newer action or staged side-table value.
        try:
            _current_state, all_events = self.claim_loop.store.snapshot(
                session_id=WORKSPACE_CLAIM_LOOP_SESSION_ID,
                loop_id=loop_id,
            )
            reserved_state = binding.get("reserved_state")
            if reserved_state is None:
                selected_prefix = self.claim_loop.store.event_prefix_result(
                    session_id=WORKSPACE_CLAIM_LOOP_SESSION_ID,
                    loop_id=loop_id,
                    idempotency_key=select_idempotency_key,
                )
                if selected_prefix is None:
                    raise WorkspaceClaimLoopError(
                        "workspace ensure selection prefix is absent"
                    )
                target_event, target_state, _target_receipt = selected_prefix
                if (
                    target_event.event_type != "ACTION_SELECTED"
                    or target_event.idempotency_key != select_idempotency_key
                ):
                    raise WorkspaceClaimLoopError(
                        "workspace ensure selection prefix is invalid"
                    )
            else:
                target_state = ClaimLoopState.model_validate(
                    reserved_state.model_dump(mode="json")
                )
                target_event = all_events[target_state.revision - 1]
            target_events = all_events[: target_state.revision]
            if (
                len(target_events) != target_state.revision
                or target_events[-1].event_sha256 != target_event.event_sha256
                or target_events[-1].event_sha256 != target_state.last_event_sha256
                or target_state.claim_id != claim_id
            ):
                raise WorkspaceClaimLoopError(
                    "workspace ensure result prefix is invalid"
                )
            response_material = self._view_material(
                workspace_state=workspace_state,
                state=target_state,
                events=target_events,
                bundle=bundle,
                include_staged_receipt=False,
            )
            response = {
                **response_material,
                "view_sha256": digest_value(response_material),
            }
        except ClaimLoopStoreError as exc:
            raise WorkspaceClaimLoopError(str(exc)) from exc
        try:
            return self.claim_loop.store.complete_client_request(
                session_id=WORKSPACE_CLAIM_LOOP_SESSION_ID,
                loop_id=loop_id,
                idempotency_key=idempotency_key,
                request_type="workspace_ensure",
                request_sha256=str(binding["request_sha256"]),
                response=response,
                completed_at=self.claim_loop._clock(),
            )
        except ClaimLoopStoreError as exc:
            raise WorkspaceClaimLoopError(str(exc)) from exc

    def _normal_state(self, workspace_state: Mapping[str, Any]) -> ClaimLoopState:
        return self._normal_snapshot(workspace_state)[0]

    def _normal_snapshot(
        self,
        workspace_state: Mapping[str, Any],
    ) -> tuple[ClaimLoopState, tuple[Any, ...]]:
        assessment_sha256 = str(
            workspace_state["intake_assessment"]["assessment_sha256"]
        )
        loop_id = self._loop_id(assessment_sha256)
        try:
            authority_store = self._authority_store_for_loop(loop_id)
            active_loop = (
                self.native_claim_loop
                if self.native_claim_loop is not None
                and authority_store is self.native_claim_loop.store
                else self.claim_loop
            )
            # Reads are also the durable recovery boundary: a committed
            # acquisition/artifact from a killed worker is reconciled into the
            # journal without invoking the adapter again.
            active_loop.state(
                session_id=WORKSPACE_CLAIM_LOOP_SESSION_ID,
                loop_id=loop_id,
            )
            state, events = active_loop.store.snapshot(
                session_id=WORKSPACE_CLAIM_LOOP_SESSION_ID,
                loop_id=loop_id,
            )
            native_binding = self._native_proposal_binding(state)
            if (native_binding is not None) != (
                active_loop is self.native_claim_loop
            ):
                raise WorkspaceClaimLoopError(
                    "workspace ClaimLoop authority selection changed"
                )
        except (ClaimLoopServiceError, ClaimLoopStoreError) as exc:
            raise WorkspaceClaimLoopError(str(exc)) from exc
        if state.claim_id != workspace_state["claim_id"]:
            raise WorkspaceClaimLoopError(
                "workspace claim loop belongs to another claim"
            )
        authority = (
            active_loop.artifact_interpreter
            if native_binding is not None
            else self.interpreter
        )
        authority_event_validator = getattr(
            authority, "validate_recorded_authority_event", None
        )
        if not callable(authority_event_validator):
            raise WorkspaceClaimLoopError(
                "workspace interpreter exposes no recorded authority validator"
            )
        try:
            for event in events:
                authority_event_validator(event)
        except (ClaimLoopError, TypeError, ValueError) as exc:
            raise WorkspaceClaimLoopError(
                "workspace journal authority chain failed closed"
            ) from exc
        return state, events

    def _correction_candidate(
        self,
        state: ClaimLoopState,
        events: tuple[Any, ...],
    ) -> dict[str, Any] | None:
        if state.active_dispatch_sha256 is not None:
            return None
        if not events:
            raise WorkspaceClaimLoopError("workspace correction journal is empty")
        for entry in reversed(state.projection_ledger):
            if entry.kind != "observation":
                continue
            artifact = self.claim_loop.store.tool_artifact(
                entry.artifact_receipt_sha256
            )
            if artifact is None:
                raise WorkspaceClaimLoopError(
                    "workspace observation artifact is unavailable"
                )
            try:
                result = self.correction_adapter.execute(
                    source_artifact=artifact,
                    state=state,
                    timestamp=events[-1].created_at,
                )
            except ClaimLoopError:
                continue
            observation = artifact.observation
            fact = next(
                value
                for value in state.facts
                if value.get("fact_id") == observation.fact_id
            )
            evidence = next(
                value
                for value in state.checklist.get("items", [])
                if value.get("item_id") == observation.evidence_item_id
            )
            proposed = result.effect.model_dump(mode="json")
            payload = {
                "contract": "casepath.workspace-correction-candidate/1.0.0",
                "claim_id": state.claim_id,
                "loop_id": state.loop_id,
                "revision": state.revision,
                "state_sha256": state.state_sha256,
                "source_artifact_receipt_sha256": artifact.receipt_sha256,
                "source_observation_sha256": observation.observation_sha256,
                "target_action_id": artifact.action_id,
                "target_fact_id": observation.fact_id,
                "target_evidence_item_id": observation.evidence_item_id,
                "current_semantics": {
                    "fact_state": fact.get("state"),
                    "normalized_value": fact.get("normalized_value"),
                    "value": fact.get("value"),
                    "explanation": fact.get("explanation"),
                    "evidence_status": evidence.get("status"),
                },
                "proposed_semantics": proposed,
                "authority_adapter_id": self.correction_adapter.adapter_id,
                "operation": "withdraw_decision_sufficiency",
            }
            return {**payload, "candidate_sha256": digest_value(payload)}
        return None

    def _latest_correction(
        self,
        *,
        state: ClaimLoopState,
        events: tuple[Any, ...],
    ) -> dict[str, Any] | None:
        for event in reversed(events):
            if event.event_type != "CORRECTION_APPLIED":
                continue
            try:
                correction = ScopedCorrection.model_validate(
                    event.command["correction"]
                )
                artifact = CorrectionArtifactReceipt.model_validate(
                    event.command["correction_artifact_receipt"]
                )
                cycle = SixAgentCycleReceipt.model_validate(
                    event.command["six_agent_cycle_receipt"]
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise WorkspaceClaimLoopError(
                    "journaled workspace correction is invalid"
                ) from exc
            payload = {
                "contract": "casepath.workspace-correction-delta/1.0.0",
                "event_type": event.event_type,
                "event_sha256": event.event_sha256,
                "correction_id": correction.correction_id,
                "correction_sha256": correction.correction_sha256,
                "correction_artifact_receipt_sha256": artifact.receipt_sha256,
                "fact_id": correction.effect.fact_id,
                "evidence_item_id": correction.effect.evidence_item_id,
                "before_fact_sha256": artifact.before_fact_sha256,
                "after_fact_sha256": artifact.expected_after_fact_sha256,
                "before_evidence_sha256": artifact.before_evidence_sha256,
                "after_evidence_sha256": artifact.expected_after_evidence_sha256,
                "unrelated_facts_before_sha256": (
                    artifact.unrelated_facts_before_sha256
                ),
                "unrelated_facts_after_sha256": (
                    artifact.unrelated_facts_after_sha256
                ),
                "rollback_fact_sha256": artifact.rollback_fact_sha256,
                "rollback_evidence_sha256": artifact.rollback_evidence_sha256,
                "before_semantics": deepcopy(event.command["before_semantics"]),
                "after_semantics": deepcopy(event.command["after_semantics"]),
                "effect": correction.effect.model_dump(mode="json"),
                "cycle_receipt_sha256": cycle.receipt_sha256,
            }
            return {**payload, "delta_sha256": digest_value(payload)}
        return None

    def correction_options(self, claim_id: str) -> dict[str, Any]:
        workspace_state = self._workspace_state(claim_id)
        state, events = self._normal_snapshot(workspace_state)
        candidate = self._correction_candidate(state, events)
        payload = {
            "contract": "casepath.workspace-correction-options/1.0.0",
            "claim_id": claim_id,
            "loop_id": state.loop_id,
            "revision": state.revision,
            "state_sha256": state.state_sha256,
            "candidates": [candidate] if candidate is not None else [],
        }
        return {**payload, "options_sha256": digest_value(payload)}

    def prepare_correction(
        self,
        claim_id: str,
        *,
        candidate_sha256: str,
        expected_revision: int,
        expected_state_sha256: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        workspace_state = self._workspace_state(claim_id)
        assessment_sha256 = str(
            workspace_state["intake_assessment"]["assessment_sha256"]
        )
        loop_id = self._loop_id(assessment_sha256)
        try:
            binding = self.claim_loop._bind_client_request(
                session_id=WORKSPACE_CLAIM_LOOP_SESSION_ID,
                loop_id=loop_id,
                idempotency_key=idempotency_key,
                request_type="workspace_prepare_correction",
                request={
                    "claim_id": claim_id,
                    "candidate_sha256": candidate_sha256,
                    "expected_revision": expected_revision,
                    "expected_state_sha256": expected_state_sha256,
                },
            )
        except ClaimLoopServiceError as exc:
            raise WorkspaceClaimLoopError(
                str(exc), conflict_envelope=exc.conflict_envelope
            ) from exc
        if binding["response"] is not None:
            return dict(binding["response"])

        def terminal_preview_failure(detail: str) -> None:
            try:
                self.claim_loop._supersede_client_request(
                    session_id=WORKSPACE_CLAIM_LOOP_SESSION_ID,
                    loop_id=loop_id,
                    idempotency_key=idempotency_key,
                    request_type="workspace_prepare_correction",
                    request_sha256=binding["request_sha256"],
                    detail=detail,
                )
            except ClaimLoopServiceError as exc:
                raise WorkspaceClaimLoopError(
                    str(exc), conflict_envelope=exc.conflict_envelope
                ) from exc
            raise AssertionError("supersession returned")  # pragma: no cover

        state = binding.get("reserved_state")
        if not isinstance(state, ClaimLoopState):
            terminal_preview_failure(
                "workspace correction preview lacks its reserved journal prefix"
            )
        try:
            all_events = self.claim_loop.store.events(
                session_id=state.session_id,
                loop_id=state.loop_id,
            )
        except ClaimLoopStoreError as exc:
            terminal_preview_failure(str(exc))
        events = all_events[: state.revision]
        if (
            len(events) != state.revision
            or not events
            or events[-1].event_sha256 != state.last_event_sha256
        ):
            terminal_preview_failure(
                "workspace correction preview journal prefix is unavailable"
            )
        candidate = self._correction_candidate(state, events)
        if (
            candidate is None
            or candidate["candidate_sha256"] != candidate_sha256
            or state.revision != expected_revision
            or state.state_sha256 != expected_state_sha256
        ):
            terminal_preview_failure(
                "workspace correction candidate is stale or unavailable"
            )
        try:
            current = self._normal_state(workspace_state)
        except WorkspaceClaimLoopError as exc:
            terminal_preview_failure(str(exc))
        if current.state_sha256 != state.state_sha256:
            terminal_preview_failure("workspace correction preview prefix changed")
        try:
            correction = self.claim_loop.register_correction(
                session_id=state.session_id,
                loop_id=state.loop_id,
                source_artifact_receipt_sha256=candidate[
                    "source_artifact_receipt_sha256"
                ],
                correction_adapter_id=self.correction_adapter.adapter_id,
                issued_at=binding["created_at"],
                expected_parent_state_sha256=state.state_sha256,
                expected_effect=candidate["proposed_semantics"],
            )
        except ClaimLoopServiceError as exc:
            terminal_preview_failure(str(exc))
        artifact = self.claim_loop.store.correction_artifact(
            correction.correction_artifact_receipt_sha256
        )
        if artifact is None:
            terminal_preview_failure(
                "workspace correction preview authority was not persisted"
            )
        preview_ledger = (
            *state.projection_ledger,
            ProjectionLedgerEntry(
                kind="correction",
                record_sha256=correction.correction_sha256,
                artifact_receipt_sha256=(
                    correction.source_artifact_receipt_sha256
                ),
                recorded_at=correction.effective_at,
            ),
        )
        projected = project_claim_loop_artifacts_v1(
            accepted=state.accepted_artifacts,
            observations=state.observations,
            corrections=(*state.corrections, correction),
            projection_ledger=preview_ledger,
        )
        projected_fact = next(
            value
            for value in projected["facts"]
            if value.get("fact_id") == correction.effect.fact_id
        )
        projected_evidence = next(
            value
            for value in projected["checklist"]["items"]
            if value.get("item_id") == correction.effect.evidence_item_id
        )
        expected_after_semantics = {
            "fact_state": projected_fact.get("state"),
            "normalized_value": projected_fact.get("normalized_value"),
            "value": projected_fact.get("value"),
            "explanation": projected_fact.get("explanation"),
            "evidence_status": projected_evidence.get("status"),
        }
        payload = {
            "contract": "casepath.workspace-correction-preview/1.0.0",
            "claim_id": claim_id,
            "loop_id": state.loop_id,
            "revision": state.revision,
            "state_sha256": state.state_sha256,
            "candidate_sha256": candidate_sha256,
            "correction_id": correction.correction_id,
            "correction_sha256": correction.correction_sha256,
            "scope": correction.scope.model_dump(mode="json"),
            "effect": correction.effect.model_dump(mode="json"),
            "preview": {
                "correction_artifact_receipt_sha256": artifact.receipt_sha256,
                "before_fact_sha256": artifact.before_fact_sha256,
                "expected_after_fact_sha256": artifact.expected_after_fact_sha256,
                "before_evidence_sha256": artifact.before_evidence_sha256,
                "expected_after_evidence_sha256": (
                    artifact.expected_after_evidence_sha256
                ),
                "unrelated_facts_before_sha256": (
                    artifact.unrelated_facts_before_sha256
                ),
                "unrelated_facts_after_sha256": (
                    artifact.unrelated_facts_after_sha256
                ),
                "rollback_fact_sha256": artifact.rollback_fact_sha256,
                "rollback_evidence_sha256": artifact.rollback_evidence_sha256,
                "before_semantics": candidate["current_semantics"],
                "expected_after_semantics": expected_after_semantics,
                "operation": candidate["operation"],
            },
        }
        response = {**payload, "response_sha256": digest_value(payload)}
        try:
            return self.claim_loop.store.complete_client_request(
                session_id=state.session_id,
                loop_id=state.loop_id,
                idempotency_key=idempotency_key,
                request_type="workspace_prepare_correction",
                request_sha256=binding["request_sha256"],
                response=response,
                completed_at=self.claim_loop._clock(),
            )
        except ClaimLoopStoreError as exc:
            raise WorkspaceClaimLoopError(str(exc)) from exc

    def apply_workspace_correction(
        self,
        claim_id: str,
        *,
        correction_id: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        workspace_state = self._workspace_state(claim_id)
        state = self._normal_state(workspace_state)
        try:
            return self.claim_loop.apply_correction(
                session_id=state.session_id,
                loop_id=state.loop_id,
                correction_id=correction_id,
                idempotency_key=idempotency_key,
            )
        except ClaimLoopServiceError as exc:
            raise WorkspaceClaimLoopError(
                str(exc), conflict_envelope=exc.conflict_envelope
            ) from exc

    def _view_material(
        self,
        *,
        workspace_state: Mapping[str, Any],
        state: ClaimLoopState,
        events: tuple[Any, ...],
        bundle: WorkspacePlaybookBundleV1,
        include_staged_receipt: bool = True,
    ) -> dict[str, Any]:
        accepted_package = state.accepted_artifacts.get("observable_package")
        accepted_binding = (
            accepted_package.get("workspace_binding")
            if isinstance(accepted_package, Mapping)
            else None
        )
        if (
            state.claim_id != workspace_state["claim_id"]
            or state.accepted_artifacts.get("playbook_template")
            != bundle.template.receipt
            or accepted_binding != bundle.observable_package.get("workspace_binding")
        ):
            raise WorkspaceClaimLoopError(
                "workspace claim loop differs from its accepted intake"
            )
        native_proposal_binding = self._native_proposal_binding(state)
        active_loop = (
            self.native_claim_loop
            if native_proposal_binding is not None
            else self.claim_loop
        )
        if active_loop is None:
            raise WorkspaceClaimLoopError(
                "native workspace ClaimLoop authority is unavailable"
            )
        phase = state.phase.value
        selected = state.selected_action
        interactive_action = selected if phase == "awaiting_observation" else None
        input_contract = (
            self.interpreter.input_contract(
                action=interactive_action,
                state=state,
            )
            if interactive_action is not None and native_proposal_binding is None
            else None
        )
        # A browser may request acquisition and echo bytes, but it never sees
        # or selects the server's finding/branch catalog.
        finding_options: list[dict[str, str]] = []
        stage = None
        if (
            include_staged_receipt
            and interactive_action is not None
            and native_proposal_binding is None
        ):
            stage = self.adapter.staged(
                session_id=state.session_id,
                loop_id=state.loop_id,
                parent_revision=state.revision,
                action_sha256=interactive_action.action_sha256,
            )
        try:
            audit = active_loop.audit_from_snapshot(state=state, events=events)
        except ClaimLoopServiceError as exc:
            raise WorkspaceClaimLoopError(str(exc)) from exc
        terminal = phase in {"decision_ready", "abstained"}
        expected_terminal_mode = (
            "finalize"
            if phase == "decision_ready"
            else "abstain"
            if phase == "abstained"
            else None
        )
        if state.terminal_mode != expected_terminal_mode:
            raise WorkspaceClaimLoopError(
                "claim loop phase and terminal authority differ"
            )
        packet = None
        if terminal:
            try:
                packet = active_loop.packet_from_state(state)
            except ClaimLoopServiceError as exc:
                raise WorkspaceClaimLoopError(
                    "terminal claim loop lacks its decision packet"
                ) from exc
            if not isinstance(packet, Mapping):
                raise WorkspaceClaimLoopError(
                    "terminal claim loop packet is invalid"
                )
        outcome = (
            "decision_ready"
            if phase == "decision_ready"
            else "abstain"
            if phase == "abstained"
            else "next_action"
            if interactive_action is not None
            else "processing"
        )
        correction_candidate = (
            None
            if native_proposal_binding is not None
            else self._correction_candidate(state, events)
        )
        latest_correction = self._latest_correction(state=state, events=events)
        try:
            operational_projection = self._scoped_operational_projection(
                derive_workspace_operational_projection_v1(
                    workspace_state=workspace_state,
                    loop_state=state,
                    loop_events=events,
                    expected_loop_id=state.loop_id,
                ),
                state,
                events,
            )
        except WorkspaceOperationalProjectionError as exc:
            raise WorkspaceClaimLoopError(str(exc)) from exc
        return {
            "contract": "casepath.workspace-claim-loop-view/2.0.0",
            "claim_id": state.claim_id,
            "revision": state.revision,
            "state_sha256": state.state_sha256,
            "workspace_revision": workspace_state["revision"],
            "workspace_state_sha256": workspace_state["state_sha256"],
            "compilation_receipt": bundle.receipt,
            "loop_state": state.model_dump(mode="json"),
            "input_contract": input_contract,
            "finding_options": finding_options,
            "stage_receipt": (
                stage.model_dump(mode="json") if stage is not None else None
            ),
            "outcome": outcome,
            "decision_packet": packet,
            "correction_count": len(state.corrections),
            "correction_candidates": (
                [correction_candidate] if correction_candidate is not None else []
            ),
            "latest_correction": latest_correction,
            "operational_projection": operational_projection,
            "audit": audit,
            "authority": "claim_loop_events",
            "provisional_source_binding": native_proposal_binding,
            "latest_proposal_revision": (
                state.native_proposal_revisions[-1].model_dump(mode="json")
                if state.native_proposal_revisions
                else None
            ),
        }

    def view(self, claim_id: str) -> dict[str, Any]:
        workspace_state = self._workspace_state(claim_id)
        state, events = self._normal_snapshot(workspace_state)
        bundle = self._bundle_from_loop(workspace_state, state)
        material = self._view_material(
            workspace_state=workspace_state,
            state=state,
            events=events,
            bundle=bundle,
        )
        return {**material, "view_sha256": digest_value(material)}

    def mint_evidence_intent(
        self,
        claim_id: str,
        *,
        action_id: str,
        expected_revision: int,
        idempotency_key: str,
        timestamp: str | None = None,
    ) -> dict[str, Any]:
        workspace_state = self._workspace_state(claim_id)
        try:
            replay = self.adapter.intent_replay(
                claim_id=claim_id,
                action_id=action_id,
                expected_revision=expected_revision,
                idempotency_key=idempotency_key,
            )
        except WorkspaceEvidenceAuthorityError as exc:
            raise WorkspaceClaimLoopError(str(exc)) from exc
        if replay is not None:
            material = {
                "contract": "casepath.workspace-acquisition-intent-response/1.0.0",
                "claim_id": claim_id,
                "loop_id": replay.loop_id,
                "recovered_durable_acquisition": False,
                "intent": replay.model_dump(mode="json"),
            }
            return {**material, "response_sha256": digest_value(material)}
        state = self._normal_state(workspace_state)
        action = state.selected_action
        if (
            state.revision != expected_revision
            or action is None
            or action.action_id != action_id
        ):
            raise WorkspaceClaimLoopError("workspace acquisition intent is stale")
        try:
            recovered = self.adapter.recoverable_acquisition(
                state=state,
                action=action,
            )
        except WorkspaceEvidenceAuthorityError as exc:
            raise WorkspaceClaimLoopError(str(exc)) from exc
        if recovered is not None:
            intent, _receipt, _raw = recovered
            material = {
                "contract": "casepath.workspace-acquisition-intent-response/1.0.0",
                "claim_id": claim_id,
                "loop_id": state.loop_id,
                "recovered_durable_acquisition": True,
                "intent": intent.model_dump(mode="json"),
            }
            return {**material, "response_sha256": digest_value(material)}
        try:
            intent = self.adapter.mint_intent(
                state=state,
                action=action,
                idempotency_key=idempotency_key,
                timestamp=timestamp,
            )
        except WorkspaceEvidenceAuthorityError as exc:
            raise WorkspaceClaimLoopError(str(exc)) from exc
        material = {
            "contract": "casepath.workspace-acquisition-intent-response/1.0.0",
            "claim_id": claim_id,
            "loop_id": state.loop_id,
            "recovered_durable_acquisition": False,
            "intent": intent.model_dump(mode="json"),
        }
        return {**material, "response_sha256": digest_value(material)}

    def acquire_evidence(
        self,
        claim_id: str,
        *,
        acquisition_intent_id: str,
        timestamp: str | None = None,
    ) -> dict[str, Any]:
        workspace_state = self._workspace_state(claim_id)
        try:
            intent = self.adapter.intent(acquisition_intent_id)
            replay = self.adapter.acquisition_for_intent(acquisition_intent_id)
        except WorkspaceEvidenceAuthorityError as exc:
            raise WorkspaceClaimLoopError(str(exc)) from exc
        if intent.claim_id != claim_id:
            raise WorkspaceClaimLoopError("workspace source acquisition is cross-claim")
        if replay is not None:
            import base64

            receipt, raw = replay
            material = {
                "contract": "casepath.workspace-source-acquisition-response/1.0.0",
                "claim_id": claim_id,
                "loop_id": receipt.loop_id,
                "content_b64": base64.b64encode(raw).decode("ascii"),
                "acquisition_receipt": receipt.model_dump(mode="json"),
            }
            return {**material, "response_sha256": digest_value(material)}
        state = self._normal_state(workspace_state)
        action = state.selected_action
        if action is None:
            raise WorkspaceClaimLoopError("workspace source acquisition has no action")
        try:
            source_entry = self.interpreter.source_candidate(action=action, state=state)
            receipt, raw = self.adapter.acquire(
                state=state,
                action=action,
                intent_id=acquisition_intent_id,
                source_entry=source_entry,
                timestamp=timestamp,
            )
        except (ClaimLoopError, WorkspaceEvidenceAuthorityError) as exc:
            raise WorkspaceClaimLoopError(str(exc)) from exc
        import base64

        material = {
            "contract": "casepath.workspace-source-acquisition-response/1.0.0",
            "claim_id": claim_id,
            "loop_id": state.loop_id,
            "content_b64": base64.b64encode(raw).decode("ascii"),
            "acquisition_receipt": receipt.model_dump(mode="json"),
        }
        return {**material, "response_sha256": digest_value(material)}

    def register_evidence(
        self,
        claim_id: str,
        *,
        schema: str,
        action_id: str,
        expected_revision: int,
        idempotency_key: str,
        acquisition_intent_id: str,
        acquisition_receipt_id: str,
        content_b64: str,
        timestamp: str | None = None,
    ) -> dict[str, Any]:
        workspace_state = self._workspace_state(claim_id)
        try:
            replay = self.adapter.registration_replay(
                claim_id=claim_id,
                schema=schema,
                action_id=action_id,
                expected_revision=expected_revision,
                idempotency_key=idempotency_key,
                acquisition_intent_id=acquisition_intent_id,
                acquisition_receipt_id=acquisition_receipt_id,
                content_b64=content_b64,
            )
        except WorkspaceEvidenceAuthorityError as exc:
            raise WorkspaceClaimLoopError(str(exc)) from exc
        if replay is not None:
            material = {
                "contract": "casepath.workspace-evidence-registration-response/1.0.0",
                "claim_id": claim_id,
                "loop_id": replay.loop_id,
                "parent_revision": replay.parent_revision,
                "parent_state_sha256": replay.parent_state_sha256,
                "stage_receipt": replay.model_dump(mode="json"),
            }
            return {**material, "response_sha256": digest_value(material)}
        state = self._normal_state(workspace_state)
        action = state.selected_action
        if action is None or action.action_id != action_id:
            raise WorkspaceClaimLoopError("workspace evidence registration is stale")
        try:
            receipt = self.adapter.register(
                state=state,
                action=action,
                schema=schema,
                expected_revision=expected_revision,
                idempotency_key=idempotency_key,
                acquisition_intent_id=acquisition_intent_id,
                acquisition_receipt_id=acquisition_receipt_id,
                content_b64=content_b64,
                timestamp=timestamp,
            )
        except WorkspaceEvidenceAuthorityError as exc:
            raise WorkspaceClaimLoopError(str(exc)) from exc
        material = {
            "contract": "casepath.workspace-evidence-registration-response/1.0.0",
            "claim_id": claim_id,
            "loop_id": state.loop_id,
            "parent_revision": state.revision,
            "parent_state_sha256": state.state_sha256,
            "stage_receipt": receipt.model_dump(mode="json"),
        }
        return {**material, "response_sha256": digest_value(material)}

    def advance(
        self,
        claim_id: str,
        *,
        expected_revision: int,
        expected_state_sha256: str,
        action_sha256: str,
        stage_receipt_sha256: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        workspace_state = self._workspace_state(claim_id)
        loop_id = self._loop_id(
            str(workspace_state["intake_assessment"]["assessment_sha256"])
        )
        stage = self.adapter.staged(
            session_id=WORKSPACE_CLAIM_LOOP_SESSION_ID,
            loop_id=loop_id,
            parent_revision=expected_revision,
            action_sha256=action_sha256,
        )
        if (
            stage is None
            or stage.claim_id != claim_id
            or stage.parent_state_sha256 != expected_state_sha256
            or stage.action_sha256 != action_sha256
            or stage.receipt_sha256 != stage_receipt_sha256
        ):
            raise WorkspaceClaimLoopError(
                "workspace advance requires exact staged evidence"
            )
        admission = {
            "contract": "casepath.workspace-advance-admission/1.0.0",
            "claim_id": claim_id,
            "loop_id": loop_id,
            "expected_revision": expected_revision,
            "expected_state_sha256": expected_state_sha256,
            "action_id": stage.action_id,
            "action_sha256": stage.action_sha256,
            "stage_receipt_sha256": stage.receipt_sha256,
            "adapter_id": WORKSPACE_EVIDENCE_ADAPTER_ID,
            "adapter_implementation_sha256": self.adapter.implementation_sha256,
        }
        request_context_sha256 = digest_value(admission)
        underlying_request = {
            "expected_revision": expected_revision,
            "requested_adapter_id": WORKSPACE_EVIDENCE_ADAPTER_ID,
            "request_context_sha256": request_context_sha256,
        }
        try:
            existing = self.claim_loop.store.lookup_client_request(
                session_id=WORKSPACE_CLAIM_LOOP_SESSION_ID,
                loop_id=loop_id,
                idempotency_key=idempotency_key,
                request_type="advance",
                request=underlying_request,
            )
        except ClaimLoopStoreError as exc:
            raise WorkspaceClaimLoopError(str(exc)) from exc
        if existing is not None and existing.get("response") is not None:
            response = existing["response"]
        else:
            if existing is None:
                state = self._normal_state(workspace_state)
                if (
                    state.session_id != WORKSPACE_CLAIM_LOOP_SESSION_ID
                    or state.loop_id != loop_id
                    or state.revision != expected_revision
                    or state.state_sha256 != expected_state_sha256
                    or state.selected_action is None
                    or state.selected_action.action_id != stage.action_id
                    or state.selected_action.action_sha256 != action_sha256
                ):
                    raise WorkspaceClaimLoopError("workspace advance proposal is stale")
            try:
                response = self.claim_loop.advance(
                    session_id=WORKSPACE_CLAIM_LOOP_SESSION_ID,
                    loop_id=loop_id,
                    idempotency_key=idempotency_key,
                    adapter_id=WORKSPACE_EVIDENCE_ADAPTER_ID,
                    expected_revision=expected_revision,
                    request_context_sha256=request_context_sha256,
                )
            except ClaimLoopServiceError as exc:
                raise WorkspaceClaimLoopError(str(exc)) from exc
        material = {
            "contract": "casepath.workspace-claim-loop-advance-response/1.0.0",
            "claim_id": claim_id,
            "loop_id": loop_id,
            "admission": admission,
            "request_context_sha256": request_context_sha256,
            "claim_loop_response": response,
        }
        return {**material, "response_sha256": digest_value(material)}

    def export(self, claim_id: str) -> dict[str, Any]:
        view = self.view(claim_id)
        material = {
            "contract": "casepath.workspace-claim-loop-export/1.0.0",
            "claim_id": claim_id,
            "workspace_state_sha256": view["workspace_state_sha256"],
            "compilation_receipt_sha256": view["compilation_receipt"]["receipt_sha256"],
            "loop_state_sha256": view["loop_state"]["state_sha256"],
            "loop_audit_sha256": view["audit"]["receipt_sha256"],
            "outcome": view["outcome"],
            "decision_packet": view["decision_packet"],
        }
        return {**material, "export_sha256": digest_value(material)}


def _node(
    row: Mapping[str, Any],
    *,
    fact_id: str | None,
    evidence_item_id: str | None,
    branches: list[dict[str, str]],
) -> dict[str, Any]:
    node_id = str(row["node_id"])
    return {
        "node_id": node_id,
        "title": str(row["label"]),
        "question": str(row["assertion"]),
        "state": "future",
        "answer": "Not reached",
        "why": str(row["assertion"]),
        "kind": "decision" if fact_id is not None else "process",
        "main_spine": True,
        "fact_ids": [fact_id] if fact_id is not None else [],
        "legal_source_ids": [],
        "evidence_requirement_ids": (
            [evidence_item_id] if evidence_item_id is not None else []
        ),
        "branches": branches,
        "activation": "always",
    }


def build_workspace_playbook_v1(
    *, corpus: PublicCorpus, claim_id: str, assessment: Mapping[str, Any]
) -> WorkspacePlaybookBundleV1:
    """Compile the complete reachable public-policy route without target access."""

    try:
        expected_assessment = validate_recorded_intake_assessment(
            json.loads(json.dumps(assessment)),
            corpus=corpus,
            claim_id=claim_id,
        )
    except (IntakeCompilationError, TypeError, ValueError) as exc:
        raise WorkspaceClaimLoopError(
            "workspace playbook input does not bind the public claim"
        ) from exc
    binding = corpus.binding(claim_id)
    claim = corpus.claim(claim_id)
    policy = corpus.static_policy()
    matches = [
        value
        for value in policy["templates"]
        if value.get("template_id")
        == expected_assessment.get("policy_template", {}).get("template_id")
    ]
    if len(matches) != 1:
        raise WorkspaceClaimLoopError("workspace policy template is ambiguous")
    policy_template = matches[0]
    catalog = policy_template.get("process_catalog")
    nodes = catalog.get("nodes") if isinstance(catalog, Mapping) else None
    transitions = catalog.get("transitions") if isinstance(catalog, Mapping) else None
    if not isinstance(nodes, list) or not isinstance(transitions, list):
        raise WorkspaceClaimLoopError("workspace policy process is invalid")
    current_node_id = expected_assessment["current_node"]["node_id"]
    node_by_id = {
        value.get("node_id"): value for value in nodes if isinstance(value, Mapping)
    }
    if current_node_id not in node_by_id:
        raise WorkspaceClaimLoopError("workspace current policy node is invalid")
    transition_rows = [
        dict(value) for value in transitions if isinstance(value, Mapping)
    ]
    if any(
        value.get("source_node_id") not in node_by_id
        or value.get("target_node_id") not in node_by_id
        for value in transition_rows
    ):
        raise WorkspaceClaimLoopError("workspace policy transition is not closed")
    outgoing_by_source: dict[str, list[dict[str, Any]]] = {}
    for value in transition_rows:
        outgoing_by_source.setdefault(str(value["source_node_id"]), []).append(value)
    for values in outgoing_by_source.values():
        values.sort(key=lambda value: str(value["edge_id"]))
    reachable = {current_node_id}
    frontier = [current_node_id]
    while frontier:
        source = frontier.pop()
        for value in outgoing_by_source.get(source, []):
            target = str(value["target_node_id"])
            if target not in reachable:
                reachable.add(target)
                frontier.append(target)
    reachable_rows = [
        dict(value)
        for value in nodes
        if isinstance(value, Mapping) and value.get("node_id") in reachable
    ]
    decision_rows = [
        value
        for value in reachable_rows
        if outgoing_by_source.get(str(value["node_id"]))
    ]
    if (
        not decision_rows
        or decision_rows[0]["node_id"] != current_node_id
        or len(decision_rows) > 16
    ):
        raise WorkspaceClaimLoopError(
            "workspace reachable decision route exceeds the closed compiler"
        )
    decision_index = {
        str(value["node_id"]): index for index, value in enumerate(decision_rows)
    }

    message = claim.get("customer_message")
    if not isinstance(message, Mapping):
        raise WorkspaceClaimLoopError("workspace claim message is invalid")
    message_id = str(message.get("message_id"))
    message_body = str(message.get("body"))
    message_passages = [
        " ".join(line.split()) for line in message_body.splitlines() if line.strip()
    ]
    raw_message_matches = [
        value
        for value in binding["observable_artifacts"]
        if value.get("artifact_id") == message_id
    ]
    if len(raw_message_matches) != 1 or not message_body or not message_passages:
        raise WorkspaceClaimLoopError("workspace claim message binding is invalid")
    message_artifact = raw_message_matches[0]
    message_projection = message_body + "\n"
    message_projection_sha256 = sha256(
        message_projection.encode("utf-8")
    ).hexdigest()
    registry = corpus.source_registry(claim_id)
    source_entries: list[dict[str, Any]] = []
    for registry_entry in registry["entries"]:
        if not isinstance(registry_entry, Mapping) or (
            registry_entry.get("source_kind") != "observable_message_span"
            or registry_entry.get("support_scope") != "case_specific"
        ):
            continue
        locator = registry_entry.get("locator")
        if not isinstance(locator, Mapping):
            raise WorkspaceClaimLoopError("workspace source locator is invalid")
        start = locator.get("text_start")
        end = locator.get("text_end")
        exact_text = locator.get("exact_text")
        if (
            locator.get("locator_kind") != "text_span"
            or locator.get("page") != 1
            or locator.get("artifact_sha256") != message_projection_sha256
            or registry_entry.get("parent_artifact_id") != message_id
            or registry_entry.get("parent_artifact_sha256")
            != message_artifact["sha256"]
            or registry_entry.get("representation_identity")
            != "observable-claim-body+utf8-final-newline/1.0.0"
            or isinstance(start, bool)
            or not isinstance(start, int)
            or isinstance(end, bool)
            or not isinstance(end, int)
            or start < 0
            or end <= start
            or end > len(message_projection)
            or not isinstance(exact_text, str)
            or message_projection[start:end] != exact_text
        ):
            raise WorkspaceClaimLoopError(
                "workspace message span differs from its source registry"
            )
        entry_material = {
            "contract": "casepath.workspace-admissible-source-span/1.0.0",
            "source_kind": "observable_message_span",
            "support_scope": "case_specific",
            "artifact_id": locator["artifact_id"],
            "artifact_sha256": locator["artifact_sha256"],
            "parent_artifact_id": registry_entry["parent_artifact_id"],
            "parent_artifact_sha256": registry_entry["parent_artifact_sha256"],
            "representation_identity": registry_entry["representation_identity"],
            "source_version": locator["source_version"],
            "locator_kind": "text_span",
            "page": 1,
            "text_start": start,
            "text_end": end,
            "byte_start": len(message_projection[:start].encode("utf-8")),
            "byte_end": len(message_projection[:end].encode("utf-8")),
            "exact_text": exact_text,
            "span_sha256": digest_text(exact_text),
        }
        source_entries.append(
            {
                **entry_material,
                "source_entry_sha256": digest_value(entry_material),
            }
        )
    source_entries.sort(key=lambda value: value["source_entry_sha256"])
    if not source_entries or len(source_entries) != len(
        {value["source_entry_sha256"] for value in source_entries}
    ):
        raise WorkspaceClaimLoopError("workspace source registry is not closed")
    source_ref = {
        "artifact_id": message_id,
        "locator_kind": "text_quote",
        "page": 1,
        "excerpt": message_passages[0],
        "agent": "Workspace public-source projector",
    }
    facts: list[dict[str, Any]] = []
    items: list[dict[str, Any]] = []
    decision_options: dict[str, dict[str, str]] = {}
    fail_closed: dict[str, str] = {}
    finding_labels: dict[str, str] = {}
    branches_by_node: dict[str, list[dict[str, str]]] = {}
    route_steps: list[dict[str, Any]] = []
    answer_by_node: dict[str, dict[str, str]] = {}
    gap_rows: list[dict[str, Any]] = []
    evidence_node_ids: dict[str, list[str]] = {}
    evidence_fact_ids: dict[str, str] = {}
    evidence_capabilities: dict[str, list[str]] = {}
    base_statuses: dict[str, str] = {}
    actor_grants: dict[str, dict[str, Any]] = {}
    for row in decision_rows:
        node_id = str(row["node_id"])
        fact_id = f"fact.workspace.{node_id}.transition"
        evidence_item_id = f"workspace_evidence.{node_id}"
        gap_node_id = f"workspace_evidence_gap.{node_id}"
        decision_key = f"workspace.{node_id}.transition"
        unresolved = "unresolved"
        options = {unresolved: f"workspace_transition.{node_id}.unresolved"}
        labels = {
            options[unresolved]: "The submitted evidence leaves this step unresolved"
        }
        branches = [{"branch_id": f"{node_id}.unresolved", "target": gap_node_id}]
        route_transitions: dict[str, dict[str, Any]] = {
            options[unresolved]: {
                "kind": "stop",
                "target_node_id": gap_node_id,
                "selected_branch_id": f"{node_id}.unresolved",
                "append_target": True,
            }
        }
        for edge in outgoing_by_source[node_id]:
            normalized = str(edge["edge_id"])
            target = str(edge["target_node_id"])
            decision_value = f"workspace_transition.{normalized}"
            options[normalized] = decision_value
            finding_labels[normalized] = str(edge["condition"])
            labels[decision_value] = str(edge["condition"])
            if target in decision_index:
                if decision_index[target] <= decision_index[node_id]:
                    raise WorkspaceClaimLoopError(
                        "workspace policy contains a non-forward decision cycle"
                    )
                transition_kind = "jump"
            else:
                transition_kind = "stop"
            route_transitions[decision_value] = {
                "kind": transition_kind,
                "target_node_id": target,
                "selected_branch_id": normalized,
                "append_target": True,
            }
            branches.append({"branch_id": normalized, "target": target})
        facts.append(
            {
                "fact_id": fact_id,
                "label": str(row["label"]),
                "value": "The current policy transition remains unresolved.",
                "state": "unknown",
                "explanation": (
                    "No admitted evidence yet selects this public-policy transition."
                ),
                "source_refs": [source_ref],
                "confidence": 1.0,
                "controls_process": True,
                "decision_key": decision_key,
                "normalized_value": unresolved,
                "decision_value": options[unresolved],
                "semantic_role": fact_id,
            }
        )
        items.append(
            {
                "item_id": evidence_item_id,
                "title": str(row["label"]),
                "status": "missing",
                "node_id": node_id,
                "fact_id": fact_id,
                "why": "A bounded source observation is required for this policy step.",
                "legal_basis_ids": [
                    value["clause_id"]
                    for value in expected_assessment["policy_clause_refs"]
                ],
                "artifact_ids": [],
                "acceptable_alternatives": [],
                "applies_when": "always",
                "required_level": "mandatory",
                "current_path": node_id == current_node_id,
                "node_ids": [node_id],
                "bounded_tool_id": WORKSPACE_EVIDENCE_ADAPTER_ID,
                # One initial source acquisition plus one explicit validation
                # attempt.  An inconclusive handler classification remains
                # honest evidence, but it must not create an infinite loop.
                "max_observed_attempts": 2,
            }
        )
        decision_options[decision_key] = options
        fail_closed[decision_key] = unresolved
        answer_by_node[node_id] = labels
        branches_by_node[node_id] = branches
        route_steps.append(
            {
                "node_id": node_id,
                "decision_key": decision_key,
                "transitions": route_transitions,
            }
        )
        evidence_node_ids[evidence_item_id] = [node_id]
        evidence_fact_ids[evidence_item_id] = fact_id
        evidence_capabilities[evidence_item_id] = ["browser_operator_observation"]
        base_statuses[evidence_item_id] = "missing"
        owner = str(row.get("responsibility"))
        actor_grants[evidence_item_id] = {
            "contract": "casepath.workspace-actor-grant/1.0.0",
            "actor_type": "claim_handler",
            "required_process_owner": owner,
            "authority_scope": (
                "handler_attested_case_source"
                if owner == "claim_handler"
                else "specialist_only"
            ),
            "decision_bearing": owner == "claim_handler",
        }
        gap_rows.append(
            {
                "node_id": gap_node_id,
                "title": f"Evidence needed for {row['label']}",
                "question": "Provide one bounded observation for this policy step.",
                "state": "future",
                "answer": "Not reached",
                "why": "The public-policy transition is unresolved.",
                "kind": "evidence_gap",
                "main_spine": False,
                "fact_ids": [],
                "legal_source_ids": [],
                "evidence_requirement_ids": [],
                "branches": [],
                "activation": "always",
            }
        )
    fact_id_by_node = {
        str(row["node_id"]): f"fact.workspace.{row['node_id']}.transition"
        for row in decision_rows
    }
    evidence_id_by_node = {
        str(row["node_id"]): f"workspace_evidence.{row['node_id']}"
        for row in decision_rows
    }
    process_nodes = [
        _node(
            value,
            fact_id=fact_id_by_node.get(str(value["node_id"])),
            evidence_item_id=evidence_id_by_node.get(str(value["node_id"])),
            branches=branches_by_node.get(str(value["node_id"]), []),
        )
        for value in reachable_rows
    ] + gap_rows
    edge_pairs = [
        [str(value["source_node_id"]), str(value["target_node_id"])]
        for value in transition_rows
        if value["source_node_id"] in reachable and value["target_node_id"] in reachable
    ] + [
        [str(row["node_id"]), f"workspace_evidence_gap.{row['node_id']}"]
        for row in decision_rows
    ]
    process = {
        "claim_id": claim_id,
        "nodes": process_nodes,
        "edges": [
            {"source": source, "target": target, "state": "possible"}
            for source, target in edge_pairs
        ],
        "main_spine": [str(value["node_id"]) for value in reachable_rows],
        "current_node": current_node_id,
        "selected_path": [],
        "current_overlay": {},
    }
    record = {"facts": facts, "process": process, "checklist": {"items": items}}
    legal_sources = expected_assessment["policy_clause_refs"]
    route_program = {"start_path": [], "steps": route_steps}
    template_catalog = {
        "supported_claim_ids": [claim_id],
        "claim_sha256_by_id": {claim_id: digest_value(record)},
        "decision_options": decision_options,
        "process_node_ids": [value["node_id"] for value in process_nodes],
        "process_edge_pairs": edge_pairs,
        "process_fact_ids_by_claim": {claim_id: [value["fact_id"] for value in facts]},
        "evidence_item_ids_by_claim": {claim_id: [value["item_id"] for value in items]},
        "evidence_node_ids": evidence_node_ids,
        "evidence_fact_ids_by_claim": {claim_id: evidence_fact_ids},
        "evidence_artifact_ids_by_claim": {claim_id: []},
        "base_evidence_status_by_claim": {claim_id: base_statuses},
        "legal_registry_version": (
            "workspace-static-policy."
            + expected_assessment["static_policy_file_sha256"]
        ),
        "legal_sources_sha256": digest_value(legal_sources),
        "same_six_agent_stategraph": True,
        "fail_closed_normalized_values": fail_closed,
        "route_program": route_program,
        "process_rendering_profile": {
            "answer_by_node": answer_by_node,
            "blocked_node_ids": [],
            "loop_edge_pairs": [],
            "future_edge_sources": [],
        },
        "evidence_projection_mode": "current_path_only_v1",
        "evidence_artifact_capabilities": evidence_capabilities,
        "maximum_controlling_facts": len(facts),
        "materializer_mode": "declarative_cycle_v1",
        "declarative_records": {claim_id: record},
    }
    template = PlaybookTemplate.build(
        template_id=f"casepath.workspace-current-step.{claim_id}",
        template_version="1.0.0",
        catalog=template_catalog,
    )
    admission_material = {
        "contract": "casepath.workspace-evidence-admission-policy/1.0.0",
        "policy_id": "casepath.workspace-handler-source-admission/1.0.0",
        "source_registry_file_sha256": binding["source_registry"]["sha256"],
        "source_entries": source_entries,
        "actor_grants": actor_grants,
        "positive_assertion_requires_decision_bearing_grant": True,
        "operator_note_is_evidence": False,
    }
    package = {
        "claim_id": claim_id,
        "customer_message": {
            "artifact_id": "message",
            "subject": str(message.get("subject")),
            "body": message_body,
        },
        "artifacts": [
            {
                **{
                    "artifact_id": message_id,
                    "filename": str(message_artifact["file_name"]),
                    "media_type": str(message_artifact["media_type"]),
                    "sha256": str(message_artifact["sha256"]),
                    "size_bytes": int(message_artifact["size_bytes"]),
                    "capabilities": ["observable_customer_message"],
                    "extracted_pages": [{"page": 1, "text": message_body}],
                },
                **(
                    {
                        "parsed_email": {
                            "subject": str(message.get("subject")),
                            "body": message_body,
                        }
                    }
                    if str(message_artifact["media_type"]).lower()
                    == "message/rfc822"
                    else {}
                ),
            },
            {
                "artifact_id": source_entries[0]["artifact_id"],
                "filename": f"{message_id}.message-body-projection.txt",
                "media_type": "text/plain; charset=utf-8",
                "sha256": message_projection_sha256,
                "size_bytes": len(message_projection.encode("utf-8")),
                "capabilities": ["observable_message_projection"],
                "extracted_pages": [{"page": 1, "text": message_projection}],
                "parent_artifact_id": message_id,
                "parent_artifact_sha256": str(message_artifact["sha256"]),
                "representation_identity": (
                    "observable-claim-body+utf8-final-newline/1.0.0"
                ),
            },
        ],
        "workspace_binding": {
            "binding_sha256": binding["binding_sha256"],
            "intake_assessment_sha256": expected_assessment["assessment_sha256"],
            "original_message_artifact_id": message_id,
            "original_message_sha256": str(message_artifact["sha256"]),
            "original_message_size_bytes": int(message_artifact["size_bytes"]),
            "static_template_sha256": binding["static_template_sha256"],
        },
        "workspace_evidence_admission": {
            **admission_material,
            "policy_sha256": digest_value(admission_material),
        },
    }
    legal_context = {
        "contract": "casepath.workspace-public-policy-context/1.0.0",
        "registry_version": template_catalog["legal_registry_version"],
        "sources": legal_sources,
    }
    receipt_payload = {
        "contract": "casepath.workspace-playbook-compilation/1.0.0",
        "claim_id": claim_id,
        "binding_sha256": binding["binding_sha256"],
        "assessment_sha256": expected_assessment["assessment_sha256"],
        "template_sha256": template.template_sha256,
        "observable_package_sha256": digest_value(package),
        "legal_context_sha256": digest_value(legal_context),
        "finding_labels_sha256": digest_value(finding_labels),
    }
    return WorkspacePlaybookBundleV1(
        template=template,
        observable_package=package,
        legal_context=legal_context,
        finding_labels=finding_labels,
        receipt={
            **receipt_payload,
            "receipt_sha256": digest_value(receipt_payload),
        },
    )


__all__ = [
    "WORKSPACE_CLAIM_LOOP_SESSION_ID",
    "WORKSPACE_EVIDENCE_ADAPTER_ID",
    "DeterministicTemplateCyclePipelineRouter",
    "WorkspaceBrowserEvidenceAdapterV1",
    "WorkspaceClaimLoopError",
    "WorkspaceClaimLoopServiceV1",
    "WorkspaceEvidenceStageReceiptV1",
    "WorkspacePlaybookBundleV1",
    "WorkspaceStructuredEvidenceInterpreterV1",
    "build_workspace_playbook_v1",
]
