from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
import hashlib
import os
from pathlib import Path
import stat
import tempfile
from typing import Literal

from pydantic import field_validator, model_validator

from .foundation.common import canonical_json_bytes, digest_value, is_sha256
from .foundation.contracts import FoundationModel
from .insurance_protocol_v1 import (
    AdapterDryRunReceiptV1,
    ActionIntentV1,
    ActionReceiptV1,
    LOCAL_ARTIFACT_REGISTRY_ADAPTER_ID,
    SOURCE_REGISTER_CAPABILITY,
    StagedArtifactReceiptV1,
)


class LocalArtifactRegistryError(RuntimeError):
    pass


class LocalArtifactRegistryInjectedFault(RuntimeError):
    pass


@dataclass(frozen=True)
class LocalRegistryMaterialV1:
    filename: str
    media_type: Literal["text/plain; charset=utf-8"]
    content: str
    claimed_content_sha256: str


class _RegistrationOutcomeV1(FoundationModel):
    contract: Literal["casepath.local-registration-outcome/1.0.0"] = (
        "casepath.local-registration-outcome/1.0.0"
    )
    state: Literal["COMMIT_CLAIMED", "CANCELLED"]
    effect_idempotency_key: str
    session_id: str
    loop_id: str
    claim_id: str
    record_version: str
    capability_id: Literal["source.register@1"]
    adapter_id: str
    content_sha256: str
    first_intent_sha256: str
    staged_artifact_receipt_sha256: str
    preexisting_content: bool
    claimed_at: str
    outcome_sha256: str

    @field_validator(
        "effect_idempotency_key",
        "content_sha256",
        "first_intent_sha256",
        "staged_artifact_receipt_sha256",
        "outcome_sha256",
    )
    @classmethod
    def validate_hash(cls, value: str) -> str:
        if not is_sha256(value):
            raise ValueError("registration outcome hash is invalid")
        return value

    @model_validator(mode="after")
    def validate_outcome(self) -> _RegistrationOutcomeV1:
        _parse_timestamp(self.claimed_at)
        payload = self.model_dump(mode="json", exclude={"outcome_sha256"})
        if digest_value(payload) != self.outcome_sha256:
            raise ValueError("registration outcome self-hash mismatch")
        return self


def _parse_timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise LocalArtifactRegistryError("INVALID_TIMESTAMP") from exc
    if parsed.tzinfo is None:
        raise LocalArtifactRegistryError("TIMESTAMP_REQUIRES_OFFSET")
    return parsed


def _source_sha256() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _read_regular(path: Path) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except (FileNotFoundError, OSError) as exc:
        raise LocalArtifactRegistryError("REGISTRY_RECORD_UNREADABLE") from exc
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink < 1:
            raise LocalArtifactRegistryError("REGISTRY_RECORD_NOT_REGULAR")
        chunks = []
        while True:
            chunk = os.read(descriptor, 65_536)
            if not chunk:
                break
            chunks.append(chunk)
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def _publish_new(path: Path, payload: bytes) -> bool:
    """Crash-safely publish complete bytes without overwrite."""

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


def _validated_intent(intent: ActionIntentV1) -> ActionIntentV1:
    return ActionIntentV1.model_validate(intent.model_dump(mode="json"))


def _validated_stage(staged: StagedArtifactReceiptV1) -> StagedArtifactReceiptV1:
    return StagedArtifactReceiptV1.model_validate(staged.model_dump(mode="json"))


class LocalArtifactRegistryAdapterV1:
    """Persistent, interpretation-free adapter for ``source.register@1``."""

    adapter_id = LOCAL_ARTIFACT_REGISTRY_ADAPTER_ID
    capability_id = SOURCE_REGISTER_CAPABILITY
    implementation_id = "casepath.local-artifact-registry/1.0.0"

    def __init__(
        self,
        root: str | Path,
        *,
        fault_hook: Callable[[str], None] | None = None,
    ) -> None:
        # One adapter instance has one immutable implementation identity.  A
        # source edit after authority admission cannot silently change execute
        # or recovery receipts for that already-admitted intent.
        self._implementation_source_sha256 = _source_sha256()
        self.root = Path(root).resolve()
        self.quarantine_root = self.root / "quarantine" / "sha256"
        self.stage_receipt_root = self.root / "stage-receipts"
        self.artifact_root = self.root / "artifacts" / "sha256"
        self.outcome_root = self.root / "outcomes"
        self.ack_root = self.root / "acknowledgements"
        for path in (
            self.quarantine_root,
            self.stage_receipt_root,
            self.artifact_root,
            self.outcome_root,
            self.ack_root,
        ):
            path.mkdir(parents=True, exist_ok=True)
            if path.is_symlink() or not path.is_dir():
                raise LocalArtifactRegistryError("REGISTRY_ROOT_INVALID")
            _fsync_directory(path)
        self._fault_hook = fault_hook

    @property
    def implementation_source_sha256(self) -> str:
        if _source_sha256() != self._implementation_source_sha256:
            raise LocalArtifactRegistryError("ADAPTER_SOURCE_CHANGED")
        return self._implementation_source_sha256

    @property
    def implementation_sha256(self) -> str:
        return digest_value(
            {
                "contract": "casepath.adapter-implementation-identity/1.1.0",
                "adapter_id": self.adapter_id,
                "implementation_id": self.implementation_id,
                "implementation_source_sha256": self.implementation_source_sha256,
            }
        )

    def _fault(self, phase: str) -> None:
        if self._fault_hook is not None:
            self._fault_hook(phase)

    def stage(
        self,
        *,
        session_id: str,
        loop_id: str,
        claim_id: str,
        record_version: str,
        material: LocalRegistryMaterialV1,
        staged_at: str,
    ) -> StagedArtifactReceiptV1:
        _parse_timestamp(staged_at)
        if material.media_type != "text/plain; charset=utf-8":
            raise LocalArtifactRegistryError("UNSUPPORTED_MEDIA_TYPE")
        if (
            not material.filename
            or material.filename in {".", ".."}
            or "/" in material.filename
            or "\\" in material.filename
            or not material.filename.lower().endswith(".txt")
        ):
            raise LocalArtifactRegistryError("INVALID_FILENAME")
        raw = material.content.encode("utf-8")
        if not raw or len(raw) > 100_000:
            raise LocalArtifactRegistryError("INVALID_CONTENT_SIZE")
        content_sha256 = hashlib.sha256(raw).hexdigest()
        if material.claimed_content_sha256 != content_sha256:
            raise LocalArtifactRegistryError("CONTENT_HASH_MISMATCH")
        quarantine_path = self.quarantine_root / f"{content_sha256}.txt"
        created = _publish_new(quarantine_path, raw)
        if not created and _read_regular(quarantine_path) != raw:
            raise LocalArtifactRegistryError("QUARANTINE_CONTENT_COLLISION")
        self._fault("AFTER_QUARANTINE_COMMIT")
        payload = {
            "contract": "casepath.staged-artifact-receipt/1.0.0",
            "session_id": session_id,
            "loop_id": loop_id,
            "claim_id": claim_id,
            "record_version": record_version,
            "filename": material.filename,
            "media_type": material.media_type,
            "byte_count": len(raw),
            "content_sha256": content_sha256,
            "quarantine_uri": f"casepath-quarantine://sha256/{content_sha256}",
            "staged_at": staged_at,
            "adapter_id": self.adapter_id,
        }
        receipt = StagedArtifactReceiptV1.model_validate(
            {**payload, "receipt_sha256": digest_value(payload)}
        )
        receipt_path = self.stage_receipt_root / f"{receipt.receipt_sha256}.json"
        receipt_bytes = canonical_json_bytes(receipt.model_dump(mode="json"))
        if not _publish_new(receipt_path, receipt_bytes):
            if _read_regular(receipt_path) != receipt_bytes:
                raise LocalArtifactRegistryError("STAGE_RECEIPT_COLLISION")
        return receipt

    def staged(self, receipt_sha256: str) -> StagedArtifactReceiptV1:
        if not is_sha256(receipt_sha256):
            raise LocalArtifactRegistryError("STAGE_RECEIPT_ID_INVALID")
        path = self.stage_receipt_root / f"{receipt_sha256}.json"
        try:
            receipt = StagedArtifactReceiptV1.model_validate_json(
                _read_regular(path)
            )
        except (TypeError, ValueError) as exc:
            raise LocalArtifactRegistryError("STAGE_RECEIPT_INVALID") from exc
        if receipt.receipt_sha256 != receipt_sha256:
            raise LocalArtifactRegistryError("STAGE_RECEIPT_PATH_MISMATCH")
        content_path = self.quarantine_root / f"{receipt.content_sha256}.txt"
        raw = _read_regular(content_path)
        if (
            len(raw) != receipt.byte_count
            or hashlib.sha256(raw).hexdigest() != receipt.content_sha256
        ):
            raise LocalArtifactRegistryError("QUARANTINE_BYTES_INVALID")
        return receipt

    def content(self, receipt: StagedArtifactReceiptV1) -> str:
        receipt = _validated_stage(receipt)
        canonical = self.staged(receipt.receipt_sha256)
        if canonical != receipt:
            raise LocalArtifactRegistryError("STAGE_RECEIPT_SUBSTITUTION")
        raw = _read_regular(
            self.quarantine_root / f"{canonical.content_sha256}.txt"
        )
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise LocalArtifactRegistryError("QUARANTINE_NOT_UTF8") from exc

    def dry_run(
        self,
        *,
        intent: ActionIntentV1,
        staged: StagedArtifactReceiptV1,
        evaluated_at: str,
    ) -> AdapterDryRunReceiptV1:
        intent = _validated_intent(intent)
        staged = _validated_stage(staged)
        evaluated = _parse_timestamp(evaluated_at)
        if evaluated >= _parse_timestamp(intent.expires_at):
            raise LocalArtifactRegistryError("INTENT_EXPIRED")
        canonical = self.staged(staged.receipt_sha256)
        if canonical != staged:
            raise LocalArtifactRegistryError("STAGE_RECEIPT_SUBSTITUTION")
        if (
            intent.capability_id != self.capability_id
            or intent.adapter_id != self.adapter_id
            or intent.staged_artifact_receipt_sha256 != staged.receipt_sha256
            or intent.content_sha256 != staged.content_sha256
            or intent.session_id != staged.session_id
            or intent.loop_id != staged.loop_id
            or intent.claim_id != staged.claim_id
            or intent.record_version != staged.record_version
        ):
            raise LocalArtifactRegistryError("INTENT_STAGE_BINDING_MISMATCH")
        payload = {
            "contract": "casepath.artifact-registry-dry-run/1.0.0",
            "source_state_sha256": intent.source_state_sha256,
            "proposal_sha256": intent.proposal_sha256,
            "staged_artifact_receipt_sha256": staged.receipt_sha256,
            "content_sha256": staged.content_sha256,
            "capability_id": intent.capability_id,
            "adapter_id": self.adapter_id,
            "adapter_implementation_id": self.implementation_id,
            "adapter_implementation_source_sha256": (
                self.implementation_source_sha256
            ),
            "adapter_implementation_sha256": self.implementation_sha256,
            "evaluated_at": evaluated_at,
            "would_commit": True,
        }
        receipt = AdapterDryRunReceiptV1.model_validate(
            {**payload, "receipt_sha256": digest_value(payload)}
        )
        if receipt.receipt_sha256 != intent.dry_run_receipt_sha256:
            raise LocalArtifactRegistryError("DRY_RUN_RECEIPT_MISMATCH")
        return receipt

    def _outcome_path(self, effect_key: str) -> Path:
        if not is_sha256(effect_key):
            raise LocalArtifactRegistryError("EFFECT_KEY_INVALID")
        return self.outcome_root / f"{effect_key}.json"

    def _artifact_path(self, content_sha256: str) -> Path:
        if not is_sha256(content_sha256):
            raise LocalArtifactRegistryError("CONTENT_ID_INVALID")
        return self.artifact_root / f"{content_sha256}.txt"

    def _ack_path(self, intent: ActionIntentV1) -> Path:
        path = self.ack_root / intent.effect_idempotency_key
        path.mkdir(parents=True, exist_ok=True)
        _fsync_directory(path)
        return path / f"{intent.intent_sha256}.json"

    def _ack_file_path(self, intent: ActionIntentV1) -> Path:
        if not is_sha256(intent.effect_idempotency_key) or not is_sha256(
            intent.intent_sha256
        ):
            raise LocalArtifactRegistryError("ACKNOWLEDGEMENT_ID_INVALID")
        return (
            self.ack_root
            / intent.effect_idempotency_key
            / f"{intent.intent_sha256}.json"
        )

    def _load_outcome(self, effect_key: str) -> _RegistrationOutcomeV1 | None:
        path = self._outcome_path(effect_key)
        if not path.exists():
            return None
        try:
            outcome = _RegistrationOutcomeV1.model_validate_json(
                _read_regular(path)
            )
        except (TypeError, ValueError) as exc:
            raise LocalArtifactRegistryError("OUTCOME_INVALID") from exc
        if outcome.effect_idempotency_key != effect_key:
            raise LocalArtifactRegistryError("OUTCOME_PATH_MISMATCH")
        return outcome

    @staticmethod
    def _require_outcome_binding(
        outcome: _RegistrationOutcomeV1, intent: ActionIntentV1
    ) -> None:
        if (
            outcome.effect_idempotency_key != intent.effect_idempotency_key
            or outcome.session_id != intent.session_id
            or outcome.loop_id != intent.loop_id
            or outcome.claim_id != intent.claim_id
            or outcome.record_version != intent.record_version
            or outcome.capability_id != intent.capability_id
            or outcome.adapter_id != intent.adapter_id
            or outcome.content_sha256 != intent.content_sha256
        ):
            raise LocalArtifactRegistryError("OUTCOME_INTENT_MISMATCH")

    def _receipt(
        self, *, intent: ActionIntentV1, outcome: _RegistrationOutcomeV1
    ) -> ActionReceiptV1:
        self._require_outcome_binding(outcome, intent)
        committed = outcome.state == "COMMIT_CLAIMED"
        deduplicated = outcome.preexisting_content or (
            outcome.first_intent_sha256 != intent.intent_sha256
        )
        payload = {
            "contract": "casepath.action-receipt/1.0.0",
            "status": "committed" if committed else "cancelled",
            "intent_sha256": intent.intent_sha256,
            "effect_idempotency_key": intent.effect_idempotency_key,
            "capability_id": intent.capability_id,
            "adapter_id": intent.adapter_id,
            "adapter_implementation_id": self.implementation_id,
            "adapter_implementation_source_sha256": (
                self.implementation_source_sha256
            ),
            "adapter_implementation_sha256": self.implementation_sha256,
            "content_sha256": intent.content_sha256,
            "artifact_uri": (
                f"casepath-artifact://sha256/{intent.content_sha256}"
                if committed
                else None
            ),
            "deduplicated_existing_content": deduplicated,
            "committed_at": outcome.claimed_at if committed else None,
            "reason_code": None if committed else "PRECOMMIT_CANCELLED",
            "model_calls": 0,
            "provider_calls": 0,
            "credential_reads": 0,
            "external_calls": 0,
            "cost_usd": 0.0,
        }
        return ActionReceiptV1.model_validate(
            {**payload, "receipt_sha256": digest_value(payload)}
        )

    def _publish_ack(
        self, *, intent: ActionIntentV1, outcome: _RegistrationOutcomeV1
    ) -> ActionReceiptV1:
        receipt = self._receipt(intent=intent, outcome=outcome)
        path = self._ack_path(intent)
        payload = canonical_json_bytes(receipt.model_dump(mode="json"))
        if not _publish_new(path, payload) and _read_regular(path) != payload:
            raise LocalArtifactRegistryError("ACKNOWLEDGEMENT_COLLISION")
        return receipt

    def _verify_ack_if_present(
        self, *, intent: ActionIntentV1, receipt: ActionReceiptV1
    ) -> None:
        path = self._ack_file_path(intent)
        if not path.exists():
            return
        try:
            persisted = ActionReceiptV1.model_validate_json(_read_regular(path))
        except (TypeError, ValueError) as exc:
            raise LocalArtifactRegistryError("ACKNOWLEDGEMENT_INVALID") from exc
        if persisted != receipt:
            raise LocalArtifactRegistryError("ACKNOWLEDGEMENT_COLLISION")

    def status(self, *, intent: ActionIntentV1) -> ActionReceiptV1 | None:
        intent = _validated_intent(intent)
        outcome = self._load_outcome(intent.effect_idempotency_key)
        if outcome is None:
            return None
        self._require_outcome_binding(outcome, intent)
        if outcome.state == "COMMIT_CLAIMED":
            artifact = self._artifact_path(intent.content_sha256)
            if not artifact.exists():
                payload = {
                    "contract": "casepath.action-receipt/1.0.0",
                    "status": "unknown",
                    "intent_sha256": intent.intent_sha256,
                    "effect_idempotency_key": intent.effect_idempotency_key,
                    "capability_id": intent.capability_id,
                    "adapter_id": intent.adapter_id,
                    "adapter_implementation_id": self.implementation_id,
                    "adapter_implementation_source_sha256": (
                        self.implementation_source_sha256
                    ),
                    "adapter_implementation_sha256": self.implementation_sha256,
                    "content_sha256": intent.content_sha256,
                    "artifact_uri": None,
                    "deduplicated_existing_content": False,
                    "committed_at": None,
                    "reason_code": "COMMIT_CLAIMED_RECONCILIATION_REQUIRED",
                    "model_calls": 0,
                    "provider_calls": 0,
                    "credential_reads": 0,
                    "external_calls": 0,
                    "cost_usd": 0.0,
                }
                return ActionReceiptV1.model_validate(
                    {**payload, "receipt_sha256": digest_value(payload)}
                )
            raw = _read_regular(artifact)
            if hashlib.sha256(raw).hexdigest() != intent.content_sha256:
                raise LocalArtifactRegistryError("COMMITTED_ARTIFACT_INVALID")
        receipt = self._receipt(intent=intent, outcome=outcome)
        self._verify_ack_if_present(intent=intent, receipt=receipt)
        return receipt

    def reconcile(
        self,
        *,
        intent: ActionIntentV1,
        staged: StagedArtifactReceiptV1,
    ) -> ActionReceiptV1 | None:
        intent = _validated_intent(intent)
        staged = _validated_stage(staged)
        outcome = self._load_outcome(intent.effect_idempotency_key)
        if outcome is None:
            return None
        self._require_outcome_binding(outcome, intent)
        if outcome.state == "COMMIT_CLAIMED":
            canonical = self.staged(staged.receipt_sha256)
            if canonical != staged or staged.content_sha256 != intent.content_sha256:
                raise LocalArtifactRegistryError("RECONCILIATION_STAGE_MISMATCH")
            raw = _read_regular(
                self.quarantine_root / f"{staged.content_sha256}.txt"
            )
            artifact = self._artifact_path(intent.content_sha256)
            created = _publish_new(artifact, raw)
            if not created and _read_regular(artifact) != raw:
                raise LocalArtifactRegistryError("ARTIFACT_CONTENT_COLLISION")
        return self._publish_ack(intent=intent, outcome=outcome)

    def execute(
        self,
        *,
        intent: ActionIntentV1,
        staged: StagedArtifactReceiptV1,
        executed_at: str,
    ) -> ActionReceiptV1:
        intent = _validated_intent(intent)
        staged = _validated_stage(staged)
        executed = _parse_timestamp(executed_at)
        if not _parse_timestamp(intent.created_at) <= executed < _parse_timestamp(
            intent.expires_at
        ):
            raise LocalArtifactRegistryError("INTENT_EXPIRED")
        self.dry_run(
            intent=intent,
            staged=staged,
            evaluated_at=intent.created_at,
        )
        self._fault("AFTER_STATUS_BEFORE_OUTCOME_CAS")
        existing_artifact = self._artifact_path(intent.content_sha256).exists()
        payload = {
            "contract": "casepath.local-registration-outcome/1.0.0",
            "state": "COMMIT_CLAIMED",
            "effect_idempotency_key": intent.effect_idempotency_key,
            "session_id": intent.session_id,
            "loop_id": intent.loop_id,
            "claim_id": intent.claim_id,
            "record_version": intent.record_version,
            "capability_id": intent.capability_id,
            "adapter_id": intent.adapter_id,
            "content_sha256": intent.content_sha256,
            "first_intent_sha256": intent.intent_sha256,
            "staged_artifact_receipt_sha256": staged.receipt_sha256,
            "preexisting_content": existing_artifact,
            "claimed_at": executed_at,
        }
        outcome = _RegistrationOutcomeV1.model_validate(
            {**payload, "outcome_sha256": digest_value(payload)}
        )
        outcome_bytes = canonical_json_bytes(outcome.model_dump(mode="json"))
        created = _publish_new(
            self._outcome_path(intent.effect_idempotency_key), outcome_bytes
        )
        if not created:
            outcome = self._load_outcome(intent.effect_idempotency_key)
            assert outcome is not None
            self._require_outcome_binding(outcome, intent)
            if outcome.state == "CANCELLED":
                return self._publish_ack(intent=intent, outcome=outcome)
        self._fault("AFTER_COMMIT_CLAIM_BEFORE_ARTIFACT")
        receipt = self.reconcile(intent=intent, staged=staged)
        if receipt is None:  # pragma: no cover - outcome was just persisted
            raise LocalArtifactRegistryError("OUTCOME_DISAPPEARED")
        self._fault("AFTER_ARTIFACT_BEFORE_EFFECT_RECEIPT")
        receipt = self._publish_ack(intent=intent, outcome=outcome)
        self._fault("AFTER_EFFECT_RECEIPT")
        return receipt

    def cancel(
        self,
        *,
        intent: ActionIntentV1,
        cancelled_at: str,
    ) -> ActionReceiptV1:
        intent = _validated_intent(intent)
        if _parse_timestamp(cancelled_at) < _parse_timestamp(intent.created_at):
            raise LocalArtifactRegistryError("CANCEL_PRECEDES_INTENT")
        self._fault("BEFORE_CANCEL_CAS")
        payload = {
            "contract": "casepath.local-registration-outcome/1.0.0",
            "state": "CANCELLED",
            "effect_idempotency_key": intent.effect_idempotency_key,
            "session_id": intent.session_id,
            "loop_id": intent.loop_id,
            "claim_id": intent.claim_id,
            "record_version": intent.record_version,
            "capability_id": intent.capability_id,
            "adapter_id": intent.adapter_id,
            "content_sha256": intent.content_sha256,
            "first_intent_sha256": intent.intent_sha256,
            "staged_artifact_receipt_sha256": (
                intent.staged_artifact_receipt_sha256
            ),
            "preexisting_content": False,
            "claimed_at": cancelled_at,
        }
        outcome = _RegistrationOutcomeV1.model_validate(
            {**payload, "outcome_sha256": digest_value(payload)}
        )
        outcome_bytes = canonical_json_bytes(outcome.model_dump(mode="json"))
        if not _publish_new(
            self._outcome_path(intent.effect_idempotency_key), outcome_bytes
        ):
            outcome = self._load_outcome(intent.effect_idempotency_key)
            assert outcome is not None
            self._require_outcome_binding(outcome, intent)
        self._fault("AFTER_CANCEL_CAS")
        if outcome.state == "COMMIT_CLAIMED":
            raise LocalArtifactRegistryError(
                "COMMIT_CLAIMED_REQUIRES_RECONCILIATION"
            )
        return self._publish_ack(intent=intent, outcome=outcome)

    def effect_count(self) -> int:
        count = 0
        for path in self.outcome_root.glob("*.json"):
            outcome = _RegistrationOutcomeV1.model_validate_json(
                _read_regular(path)
            )
            if outcome.state == "COMMIT_CLAIMED":
                count += 1
        return count

    def content_blob_count(self) -> int:
        return sum(
            1 for path in self.artifact_root.glob("*.txt") if path.is_file()
        )


__all__ = [
    "LocalArtifactRegistryAdapterV1",
    "LocalArtifactRegistryError",
    "LocalArtifactRegistryInjectedFault",
    "LocalRegistryMaterialV1",
]
