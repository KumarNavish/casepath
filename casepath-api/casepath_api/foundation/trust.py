from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .common import canonical_json_bytes, digest_value
from .contracts import CanonicalCaseInput, ModelArtifact, PrivacyIntake, PrivacyState
from .privacy import privacy_gate


class FoundationTrustError(RuntimeError):
    """A server-side trust assertion could not be verified."""


TEST_REGISTRY_AUTHORITY_ID = "casepath.non-human-test-dataset-authority/1.0.0"
TEST_REGISTRY_TRUST_ROOT = b"casepath-foundation-public-fixture-registry-v1"
TEST_REVIEW_TRUST_ROOT = b"casepath-foundation-non-human-review-fixture-v1"
TEST_REVIEW_PRINCIPAL_ID = "casepath-non-human-test-principal-v1"
TEST_REVIEW_ROLE = "foundation_test_reviewer"


def _iso(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise FoundationTrustError("trust timestamps must contain a timezone")
    return parsed


def _signature(payload: dict[str, Any], key: bytes) -> str:
    return hmac.new(key, canonical_json_bytes(payload), hashlib.sha256).hexdigest()


def sign_registry_manifest(payload: dict[str, Any], *, key: bytes) -> dict[str, Any]:
    """Sign a deterministic public-fixture manifest with a test-only trust root."""

    if "signature" in payload or "manifest_sha256" in payload:
        raise ValueError("unsigned registry payload must not contain signature fields")
    manifest_sha256 = digest_value(payload)
    signed_payload = {**payload, "manifest_sha256": manifest_sha256}
    return {**signed_payload, "signature": _signature(signed_payload, key)}


@dataclass(frozen=True)
class TrustedRegistryEntry:
    case_id: str
    privacy_intake: PrivacyIntake
    model_artifact: ModelArtifact
    entry_sha256: str


@dataclass(frozen=True)
class TrustedIntake:
    case_input: CanonicalCaseInput
    model_artifact: ModelArtifact
    authority_receipt: dict[str, Any]
    scan_receipt: dict[str, Any]


class TrustedDatasetRegistry:
    """Read-only, server-configured public dataset authority.

    The HTTP boundary accepts only a case ID. All trust assertions and source
    payloads come from this signed registry, never from the caller.
    """

    def __init__(
        self,
        *,
        path: Path,
        trust_root: bytes,
        now: datetime,
    ) -> None:
        self.path = path.resolve()
        self._trust_root = trust_root
        self._now = now
        self._manifest = self._load_and_verify()
        self._entries = self._load_entries()

    @property
    def manifest_sha256(self) -> str:
        return str(self._manifest["manifest_sha256"])

    @property
    def authority_id(self) -> str:
        return str(self._manifest["authority_id"])

    @property
    def dataset_id(self) -> str:
        return str(self._manifest["dataset_id"])

    @property
    def dataset_version(self) -> str:
        return str(self._manifest["dataset_version"])

    def summary(self) -> dict[str, Any]:
        payload = {
            "contract": "casepath.trusted-dataset-registry-summary/1.0.0",
            "authority_id": self.authority_id,
            "dataset_id": self.dataset_id,
            "dataset_version": self.dataset_version,
            "manifest_sha256": self.manifest_sha256,
            "case_ids": sorted(self._entries),
            "case_count": len(self._entries),
            "trust_mode": "signed_server_controlled_non_human_test_fixture",
            "scientific_nonclaim": (
                "A signed synthetic fixture registry is not evidence of general "
                "anonymization safety or human/expert review."
            ),
        }
        return {**payload, "receipt_sha256": digest_value(payload)}

    def _load_and_verify(self) -> dict[str, Any]:
        try:
            manifest = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise FoundationTrustError(
                "trusted dataset registry is unreadable"
            ) from exc
        if not isinstance(manifest, dict):
            raise FoundationTrustError("trusted dataset registry must be an object")
        required = {
            "contract",
            "authority_id",
            "dataset_id",
            "dataset_version",
            "valid_from",
            "valid_until",
            "entries",
            "manifest_sha256",
            "signature",
        }
        if set(manifest) != required:
            raise FoundationTrustError("trusted dataset registry fields mismatch")
        if manifest["contract"] != "casepath.trusted-dataset-registry/1.0.0":
            raise FoundationTrustError("trusted dataset registry contract mismatch")
        unsigned = {
            key: value
            for key, value in manifest.items()
            if key not in {"manifest_sha256", "signature"}
        }
        expected_manifest_hash = digest_value(unsigned)
        if not hmac.compare_digest(
            str(manifest["manifest_sha256"]), expected_manifest_hash
        ):
            raise FoundationTrustError("trusted dataset registry hash mismatch")
        signed_payload = {**unsigned, "manifest_sha256": expected_manifest_hash}
        expected_signature = _signature(signed_payload, self._trust_root)
        if not hmac.compare_digest(str(manifest["signature"]), expected_signature):
            raise FoundationTrustError("trusted dataset registry signature mismatch")
        if not (
            _iso(str(manifest["valid_from"]))
            <= self._now
            <= _iso(str(manifest["valid_until"]))
        ):
            raise FoundationTrustError(
                "trusted dataset registry is stale or not active"
            )
        if not isinstance(manifest["entries"], list) or not manifest["entries"]:
            raise FoundationTrustError("trusted dataset registry has no entries")
        return manifest

    def _load_entries(self) -> dict[str, TrustedRegistryEntry]:
        result: dict[str, TrustedRegistryEntry] = {}
        for raw in self._manifest["entries"]:
            if not isinstance(raw, dict) or set(raw) != {
                "case_id",
                "privacy_intake",
                "model_artifact",
                "entry_sha256",
            }:
                raise FoundationTrustError("trusted registry entry shape mismatch")
            entry_payload = {
                key: value for key, value in raw.items() if key != "entry_sha256"
            }
            if digest_value(entry_payload) != raw["entry_sha256"]:
                raise FoundationTrustError("trusted registry entry hash mismatch")
            intake = PrivacyIntake.model_validate(raw["privacy_intake"])
            artifact = ModelArtifact.model_validate(raw["model_artifact"])
            case_id = str(raw["case_id"])
            if intake.case_id != case_id or artifact.case_id != case_id:
                raise FoundationTrustError("trusted registry case identity mismatch")
            if intake.declared_synthetic_or_anonymized:
                raise FoundationTrustError(
                    "trusted registry intake must not use the client declaration field"
                )
            if case_id in result:
                raise FoundationTrustError("trusted registry case IDs must be unique")
            result[case_id] = TrustedRegistryEntry(
                case_id=case_id,
                privacy_intake=intake,
                model_artifact=artifact,
                entry_sha256=str(raw["entry_sha256"]),
            )
        return result

    def admit(self, case_id: str) -> TrustedIntake:
        entry = self._entries.get(case_id)
        if entry is None:
            raise FoundationTrustError(
                "case is not present in the trusted dataset registry"
            )
        scan = privacy_gate(entry.privacy_intake)
        if scan.state == PrivacyState.BLOCKED_FOR_UNRESOLVED_IDENTIFIERS:
            raise FoundationTrustError(
                "trusted fixture failed the deterministic privacy scan"
            )
        authority_payload = {
            "contract": "casepath.trusted-privacy-authority-receipt/1.0.0",
            "authority_id": self.authority_id,
            "dataset_id": self.dataset_id,
            "dataset_version": self.dataset_version,
            "registry_manifest_sha256": self.manifest_sha256,
            "registry_entry_sha256": entry.entry_sha256,
            "case_id": case_id,
            "decision": PrivacyState.ALREADY_SYNTHETIC_OR_ANONYMIZED.value,
            "underlying_scan_state": scan.state.value,
            "underlying_scan_receipt_sha256": scan.receipt.receipt_sha256,
            "source_lineage_sha256": scan.receipt.source_lineage_sha256,
            "input_sha256": scan.receipt.input_sha256,
            "sanitized_payload_sha256": scan.receipt.sanitized_payload_sha256,
            "server_controlled": True,
            "caller_trust_declaration_accepted": False,
            "fixture_scope_only": True,
            "safety_nonclaim": (
                "Passing signed synthetic fixtures does not establish general "
                "anonymization safety."
            ),
        }
        authority_receipt = {
            **authority_payload,
            "receipt_sha256": digest_value(authority_payload),
        }
        if scan.sanitized_message is None:
            raise FoundationTrustError("admitted fixture has no sanitized message")
        case_input = CanonicalCaseInput(
            case_id=case_id,
            language=entry.privacy_intake.language,
            claim_message=scan.sanitized_message,
            attachments=scan.sanitized_attachments,
            source_locators=scan.source_locators,
            privacy_receipt_sha256=authority_receipt["receipt_sha256"],
        )
        return TrustedIntake(
            case_input=case_input,
            model_artifact=entry.model_artifact,
            authority_receipt=authority_receipt,
            scan_receipt=scan.receipt.model_dump(mode="json"),
        )


def build_registry_entry(
    *, privacy_intake: PrivacyIntake, model_artifact: ModelArtifact
) -> dict[str, Any]:
    if privacy_intake.case_id != model_artifact.case_id:
        raise ValueError("registry entry case identity mismatch")
    if privacy_intake.declared_synthetic_or_anonymized:
        raise ValueError("registry fixtures must not carry a caller trust declaration")
    payload = {
        "case_id": privacy_intake.case_id,
        "privacy_intake": privacy_intake.model_dump(mode="json"),
        "model_artifact": model_artifact.model_dump(mode="json"),
    }
    return {**payload, "entry_sha256": digest_value(payload)}
