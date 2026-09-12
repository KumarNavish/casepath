from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Literal

from pydantic import field_validator, model_validator

from . import ecab_replay_adapter as _codec_module
from . import local_artifact_registry as _registry_module
from .claim_loop_contracts import EvidenceAction, FoundationModel
from .ecab_replay_adapter import (
    ECAB_FACTUAL_HISTORY_TOOL_ID,
    ECABFactualHistorySpanV1,
    ECABMappedReplayEventV1,
    ECABReplayContractError,
    map_ecab_factual_history_span_v1,
)
from .foundation.common import canonical_json_bytes, digest_value, is_sha256
from .insurance_protocol_v1 import StagedArtifactReceiptV1
from .local_artifact_registry import (
    LocalArtifactRegistryAdapterV1,
    LocalArtifactRegistryError,
    LocalRegistryMaterialV1,
    _fsync_directory,
    _publish_new,
    _read_regular,
)


def _source_sha256() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def _implementation_closure_sha256() -> str:
    """Bind the subclass, stateless mapper, and inherited effect engine."""

    return digest_value(
        {
            "contract": "casepath.ecab-registry-implementation-closure/1.0.0",
            "ecab_registry_adapter_v1.py": _source_sha256(),
            "ecab_replay_adapter.py": hashlib.sha256(
                Path(_codec_module.__file__).read_bytes()
            ).hexdigest(),
            "local_artifact_registry.py": hashlib.sha256(
                Path(_registry_module.__file__).read_bytes()
            ).hexdigest(),
        }
    )


class ECABMappedStageReceiptV1(FoundationModel):
    """Durable bridge from an outcome-free span to one quarantined excerpt."""

    contract: Literal["casepath.ecab-mapped-stage-receipt/1.0.0"] = (
        "casepath.ecab-mapped-stage-receipt/1.0.0"
    )
    mapped_event: ECABMappedReplayEventV1
    staged_artifact: StagedArtifactReceiptV1
    adapter_implementation_sha256: str
    receipt_sha256: str

    @field_validator("adapter_implementation_sha256", "receipt_sha256")
    @classmethod
    def validate_hash(cls, value: str) -> str:
        if not is_sha256(value):
            raise ValueError("ECAB mapped-stage hash is invalid")
        return value

    @model_validator(mode="after")
    def validate_binding(self) -> ECABMappedStageReceiptV1:
        if (
            self.staged_artifact.adapter_id != ECAB_FACTUAL_HISTORY_TOOL_ID
            or self.staged_artifact.record_version
            != self.mapped_event.artifact_source_version
            or self.staged_artifact.content_sha256 != self.mapped_event.span_sha256
            or self.staged_artifact.byte_count
            != len(self.mapped_event.sanitized_excerpt.encode("utf-8"))
        ):
            raise ValueError("ECAB mapped stage differs from its factual-history span")
        if (
            digest_value(self.model_dump(mode="json", exclude={"receipt_sha256"}))
            != self.receipt_sha256
        ):
            raise ValueError("ECAB mapped-stage receipt self-hash mismatch")
        return self


class ECABFactualHistoryRegistryAdapterV1(LocalArtifactRegistryAdapterV1):
    """Persistent adapter for an already-sanitized factual-history span.

    The stateless, I/O-free span codec remains in ``ecab_replay_adapter``.
    This implementation is a separately identified adapter on the same
    ``source.register@1`` thin-waist port; it never reads a corpus or outcome.
    """

    adapter_id = ECAB_FACTUAL_HISTORY_TOOL_ID
    implementation_id = "casepath.ecab-factual-history-registry/1.0.0"
    requires_typed_factual_history_stage = True

    def __init__(self, root: str | Path, **kwargs: Any) -> None:
        super().__init__(root, **kwargs)
        self.mapped_stage_root = self.root / "mapped-stage-receipts"
        self.mapped_stage_root.mkdir(parents=True, exist_ok=True)
        if self.mapped_stage_root.is_symlink() or not self.mapped_stage_root.is_dir():
            raise LocalArtifactRegistryError("MAPPED_STAGE_ROOT_INVALID")
        _fsync_directory(self.mapped_stage_root)
        self._implementation_source_sha256 = _implementation_closure_sha256()

    @property
    def implementation_source_sha256(self) -> str:
        current = _implementation_closure_sha256()
        if current != self._implementation_source_sha256:
            raise ECABReplayContractError("adapter source changed after binding")
        return current

    def stage(self, **_: Any) -> StagedArtifactReceiptV1:
        """Reject the inherited untyped staging bypass for this adapter."""

        raise ECABReplayContractError("ECAB_TYPED_FACTUAL_HISTORY_STAGE_REQUIRED")

    def stage_factual_history(
        self,
        *,
        session_id: str,
        loop_id: str,
        claim_id: str,
        record_version: str,
        action: EvidenceAction,
        span: ECABFactualHistorySpanV1,
        staged_at: str,
    ) -> ECABMappedStageReceiptV1:
        mapped = map_ecab_factual_history_span_v1(
            action=action,
            span=span,
            record_version=record_version,
            expected_event_index=0,
            expected_previous_event_sha256=None,
        )
        staged = super().stage(
            session_id=session_id,
            loop_id=loop_id,
            claim_id=claim_id,
            record_version=record_version,
            material=LocalRegistryMaterialV1(
                filename="factual-history-span.txt",
                media_type="text/plain; charset=utf-8",
                # Only the mapped factual-history span crosses the artifact
                # boundary.  The full sanitized page remains provenance input,
                # not silently promoted evidence.
                content=mapped.sanitized_excerpt,
                claimed_content_sha256=mapped.span_sha256,
            ),
            staged_at=staged_at,
        )
        payload = {
            "contract": "casepath.ecab-mapped-stage-receipt/1.0.0",
            "mapped_event": mapped.model_dump(mode="json"),
            "staged_artifact": staged.model_dump(mode="json"),
            "adapter_implementation_sha256": self.implementation_sha256,
        }
        receipt = ECABMappedStageReceiptV1.model_validate(
            {**payload, "receipt_sha256": digest_value(payload)}
        )
        path = self.mapped_stage_root / f"{staged.receipt_sha256}.json"
        raw = canonical_json_bytes(receipt.model_dump(mode="json"))
        if not _publish_new(path, raw) and _read_regular(path) != raw:
            raise LocalArtifactRegistryError("MAPPED_STAGE_RECEIPT_COLLISION")
        return receipt

    def staging_binding(self, receipt_sha256: str) -> ECABMappedStageReceiptV1:
        path = self.mapped_stage_root / f"{receipt_sha256}.json"
        try:
            binding = ECABMappedStageReceiptV1.model_validate_json(_read_regular(path))
        except (TypeError, ValueError) as exc:
            raise LocalArtifactRegistryError("MAPPED_STAGE_RECEIPT_INVALID") from exc
        canonical = super().staged(receipt_sha256)
        if (
            binding.staged_artifact != canonical
            or binding.adapter_implementation_sha256 != self.implementation_sha256
        ):
            raise LocalArtifactRegistryError("MAPPED_STAGE_RECEIPT_DIVERGED")
        return binding

    def staged(self, receipt_sha256: str) -> StagedArtifactReceiptV1:
        return self.staging_binding(receipt_sha256).staged_artifact


__all__ = [
    "ECABFactualHistoryRegistryAdapterV1",
    "ECABMappedStageReceiptV1",
]
