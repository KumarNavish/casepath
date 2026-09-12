from __future__ import annotations

import hashlib
import hmac
import sqlite3
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from .case_adapter import (
    assemble_canonical_artifact,
    canonical_to_benchmark,
    canonical_to_product,
)
from .common import canonical_json_bytes, content_address, digest_value
from .contracts import CanonicalCaseArtifact, KnowledgeState
from .model_boundary import DeterministicReferenceAdapter, execute_model_boundary
from .persistence import FoundationPersistenceError, PersistentFoundationStore
from .trust import (
    TEST_REVIEW_PRINCIPAL_ID,
    TEST_REVIEW_ROLE,
    TrustedDatasetRegistry,
)
from .validation import validate_canonical_artifact


class FoundationLiveError(RuntimeError):
    pass


COMPATIBILITY_MATRIX = (
    {
        "artifact_class": "foundation_live_api_payload_v1",
        "classification": "losslessly_supported",
        "adapter": "canonical FastAPI schemas with extra=forbid",
    },
    {
        "artifact_class": "foundation_sqlite_record_v1",
        "classification": "losslessly_supported",
        "adapter": "canonical JSON plus content and receipt hashes",
    },
    {
        "artifact_class": "foundation_review_ui_state_v1",
        "classification": "losslessly_supported",
        "adapter": "foundation-live.js canonical response projection",
    },
    {
        "artifact_class": "foundation_audit_export_v1",
        "classification": "losslessly_supported",
        "adapter": "immutable transaction/state-history export",
    },
    {
        "artifact_class": "casepath_product_foundation_projection_v1",
        "classification": "documented_adapter",
        "adapter": "canonical_to_product/product_to_canonical",
    },
    {
        "artifact_class": "casepath_benchmark_foundation_projection_v1",
        "classification": "documented_adapter",
        "adapter": "canonical_to_benchmark/benchmark_to_canonical",
    },
    {
        "artifact_class": "legacy_api_run_and_review_payloads_v15",
        "classification": "intentionally_deprecated",
        "adapter": "none; isolated legacy demo path cannot mutate foundation tables",
    },
    {
        "artifact_class": "legacy_sqlite_reviews_memories_candidates",
        "classification": "intentionally_deprecated",
        "adapter": "none; separate tables and no authority-bearing promotion",
    },
    {
        "artifact_class": "legacy_frontend_live_v16_review_state",
        "classification": "intentionally_deprecated",
        "adapter": "none; explicitly unverified demo review",
    },
    {
        "artifact_class": "arbitrary_historical_or_external_payload",
        "classification": "unsupported",
        "adapter": "rejected; no silent coercion",
    },
)

LEGACY_BYPASS_INVENTORY = (
    {
        "surface": "POST /api/runs/{run_id}/review",
        "classification": "legacy_unverified_demo_only",
        "foundation_mutation": False,
    },
    {
        "surface": "GET /api/knowledge and /api/learning-proof",
        "classification": "legacy_demo_store_only",
        "foundation_mutation": False,
    },
    {
        "surface": "SQLite reviews, memories, candidates tables",
        "classification": "legacy_alternate_store_isolated",
        "foundation_mutation": False,
    },
    {
        "surface": "live-v16.js simulated review controls",
        "classification": "legacy_ui_intentionally_deprecated_for_authority",
        "foundation_mutation": False,
    },
)


def _hmac(payload: dict[str, Any], key: bytes) -> str:
    return hmac.new(key, canonical_json_bytes(payload), hashlib.sha256).hexdigest()


def _receipt(
    *,
    action: str,
    version_id: str,
    state_before: str | None,
    state_after: str,
    active_before: str | None,
    active_after: str | None,
    rollback_target: str | None,
    content_sha256: str,
    provenance: list[dict[str, Any]],
    timestamp: str,
    exact_prior_version_restored: bool | None = None,
) -> dict[str, Any]:
    payload = {
        "contract": "casepath.persistent-governance-receipt/1.0.0",
        "action": action,
        "version_id": version_id,
        "state_before": state_before,
        "state_after": state_after,
        "active_before": active_before,
        "active_after": active_after,
        "rollback_target": rollback_target,
        "content_sha256": content_sha256,
        "provenance": provenance,
        "exact_prior_version_restored": exact_prior_version_restored,
        "timestamp": timestamp,
    }
    return {**payload, "receipt_sha256": digest_value(payload)}


def _record_history(
    connection: sqlite3.Connection,
    *,
    session_id: str,
    lifecycle_id: str | None,
    receipt: dict[str, Any],
) -> None:
    history_id = f"history.{receipt['receipt_sha256']}"
    connection.execute(
        """
        INSERT INTO foundation_state_history
        (session_id,history_id,version_id,lifecycle_id,state_before,state_after,action,receipt_json,created_at)
        VALUES (?,?,?,?,?,?,?,?,?)
        """,
        (
            session_id,
            history_id,
            receipt["version_id"],
            lifecycle_id,
            receipt["state_before"],
            receipt["state_after"],
            receipt["action"],
            canonical_json_bytes(receipt).decode("utf-8"),
            receipt["timestamp"],
        ),
    )


class FoundationLiveService:
    """Provider-free product service for the bounded live foundation proof."""

    def __init__(
        self,
        *,
        registry: TrustedDatasetRegistry,
        store: PersistentFoundationStore,
        review_trust_root: bytes,
        clock: Callable[[], datetime],
        revoked_principals: frozenset[str] = frozenset(),
    ) -> None:
        self.registry = registry
        self.store = store
        self._review_trust_root = review_trust_root
        self._clock = clock
        self._revoked_principals = revoked_principals

    def _timestamp(self) -> str:
        return self._clock().isoformat()

    def status(self) -> dict[str, Any]:
        payload = {
            "contract": "casepath.foundation-live-status/1.0.0",
            "status": "ready",
            "execution_mode": "deterministic_reference",
            "persistence": "sqlite",
            "review_authority": "non_human_test_fixture",
            "model_calls": 0,
            "provider_calls": 0,
            "provider_credentials_read": False,
            "cost_usd": 0.0,
            "central_hypothesis": "UNTESTED",
            "registry": self.registry.summary(),
        }
        return {**payload, "receipt_sha256": digest_value(payload)}

    def compatibility(self) -> dict[str, Any]:
        payload = {
            "contract": "casepath.native-artifact-compatibility/1.0.0",
            "matrix": list(COMPATIBILITY_MATRIX),
            "legacy_bypass_inventory": list(LEGACY_BYPASS_INVENTORY),
            "unsupported_policy": "reject_without_coercion",
        }
        return {**payload, "receipt_sha256": digest_value(payload)}

    def intake(
        self, *, session_id: str, case_id: str, idempotency_key: str
    ) -> dict[str, Any]:
        timestamp = self._timestamp()
        trusted = self.registry.admit(case_id)
        boundary = execute_model_boundary(
            DeterministicReferenceAdapter({case_id: trusted.model_artifact}),
            trusted.case_input,
        )
        candidate_content = {
            "contract": "casepath.foundation-knowledge-content/1.0.0",
            "case_id": case_id,
            "process_artifact": boundary.artifact.process_artifact,
            "evidence_document_plan": list(boundary.artifact.evidence_document_plan),
            "provenance": [
                value.model_dump(mode="json") for value in boundary.artifact.provenance
            ],
            "accepted_corrections": [],
        }
        candidate_version_id = content_address("knowledge", candidate_content)
        canonical = assemble_canonical_artifact(
            trusted.case_input,
            boundary.artifact,
            model_boundary_receipt_sha256=boundary.receipt.receipt_sha256,
            review_state=KnowledgeState.QUARANTINED.value,
            knowledge_version=candidate_version_id,
        )
        validation = validate_canonical_artifact(canonical)
        if not validation.passed:
            raise FoundationLiveError("canonical foundation validation failed")
        lifecycle_id = content_address(
            "lifecycle",
            {
                "session_id": session_id,
                "case_id": case_id,
                "canonical_sha256": canonical.canonical_sha256,
            },
        )
        provenance = [value.model_dump(mode="json") for value in canonical.provenance]
        inputs = {"case_id": case_id}

        def operation(connection: sqlite3.Connection) -> dict[str, Any]:
            session = self.store.session(connection, session_id)
            initial_receipt: dict[str, Any] | None = None
            if session is None:
                baseline_content = {
                    "contract": "casepath.foundation-baseline-knowledge/1.0.0",
                    "dataset_id": self.registry.dataset_id,
                    "dataset_version": self.registry.dataset_version,
                    "status": "public deterministic fixture baseline",
                }
                baseline_id = content_address("knowledge", baseline_content)
                baseline_sha = digest_value(baseline_content)
                snapshot = {
                    "version_id": baseline_id,
                    "content": baseline_content,
                    "content_sha256": baseline_sha,
                    "provenance": provenance,
                    "index_sha256": digest_value(
                        {"version_id": baseline_id, "case_ids": []}
                    ),
                }
                connection.execute(
                    """INSERT INTO foundation_sessions
                    (session_id,active_version_id,active_snapshot_json,active_index_sha256,created_at,updated_at)
                    VALUES (?,?,?,?,?,?)""",
                    (
                        session_id,
                        baseline_id,
                        canonical_json_bytes(snapshot).decode("utf-8"),
                        snapshot["index_sha256"],
                        timestamp,
                        timestamp,
                    ),
                )
                connection.execute(
                    """INSERT INTO foundation_versions
                    (session_id,version_id,lifecycle_id,state,content_json,content_sha256,
                    provenance_json,rollback_target,created_at,updated_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?)""",
                    (
                        session_id,
                        baseline_id,
                        None,
                        KnowledgeState.PROMOTED.value,
                        canonical_json_bytes(baseline_content).decode("utf-8"),
                        baseline_sha,
                        canonical_json_bytes(provenance).decode("utf-8"),
                        None,
                        timestamp,
                        timestamp,
                    ),
                )
                initial_receipt = _receipt(
                    action="install_initial",
                    version_id=baseline_id,
                    state_before=None,
                    state_after=KnowledgeState.PROMOTED.value,
                    active_before=None,
                    active_after=baseline_id,
                    rollback_target=None,
                    content_sha256=baseline_sha,
                    provenance=provenance,
                    timestamp=timestamp,
                )
                _record_history(
                    connection,
                    session_id=session_id,
                    lifecycle_id=None,
                    receipt=initial_receipt,
                )
                session = self.store.session(connection, session_id)
            if session is None or session["active_version_id"] is None:
                raise FoundationLiveError("active rollback target is missing")
            if self.store.lifecycle(connection, session_id, lifecycle_id) is not None:
                raise FoundationLiveError(
                    "lifecycle already exists outside idempotency journal"
                )
            candidate_with_rollback = {
                **candidate_content,
                "rollback_snapshot": session["active_snapshot"],
            }
            candidate_sha = digest_value(candidate_with_rollback)
            candidate_version = content_address("knowledge", candidate_with_rollback)
            if candidate_version != candidate_version_id:
                # Keep canonical identity tied to the actual content-addressed version.
                candidate_version_id_local = candidate_version
                canonical_local = assemble_canonical_artifact(
                    trusted.case_input,
                    boundary.artifact,
                    model_boundary_receipt_sha256=boundary.receipt.receipt_sha256,
                    review_state=KnowledgeState.QUARANTINED.value,
                    knowledge_version=candidate_version_id_local,
                )
                validation_local = validate_canonical_artifact(canonical_local)
            else:
                candidate_version_id_local = candidate_version_id
                canonical_local = canonical
                validation_local = validation
            if not validation_local.passed:
                raise FoundationLiveError("canonical foundation validation failed")
            connection.execute(
                """INSERT INTO foundation_versions
                (session_id,version_id,lifecycle_id,state,content_json,content_sha256,
                provenance_json,rollback_target,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (
                    session_id,
                    candidate_version_id_local,
                    lifecycle_id,
                    KnowledgeState.CANDIDATE.value,
                    canonical_json_bytes(candidate_with_rollback).decode("utf-8"),
                    candidate_sha,
                    canonical_json_bytes(provenance).decode("utf-8"),
                    session["active_version_id"],
                    timestamp,
                    timestamp,
                ),
            )
            candidate_receipt = _receipt(
                action="create_candidate",
                version_id=candidate_version_id_local,
                state_before=None,
                state_after=KnowledgeState.CANDIDATE.value,
                active_before=session["active_version_id"],
                active_after=session["active_version_id"],
                rollback_target=session["active_version_id"],
                content_sha256=candidate_sha,
                provenance=provenance,
                timestamp=timestamp,
            )
            _record_history(
                connection,
                session_id=session_id,
                lifecycle_id=lifecycle_id,
                receipt=candidate_receipt,
            )
            quarantine_receipt = _receipt(
                action="quarantine",
                version_id=candidate_version_id_local,
                state_before=KnowledgeState.CANDIDATE.value,
                state_after=KnowledgeState.QUARANTINED.value,
                active_before=session["active_version_id"],
                active_after=session["active_version_id"],
                rollback_target=session["active_version_id"],
                content_sha256=candidate_sha,
                provenance=provenance,
                timestamp=timestamp,
            )
            connection.execute(
                """UPDATE foundation_versions SET state=?,updated_at=?
                WHERE session_id=? AND version_id=?""",
                (
                    KnowledgeState.QUARANTINED.value,
                    timestamp,
                    session_id,
                    candidate_version_id_local,
                ),
            )
            _record_history(
                connection,
                session_id=session_id,
                lifecycle_id=lifecycle_id,
                receipt=quarantine_receipt,
            )
            canonical_json = canonical_local.model_dump(mode="json")
            connection.execute(
                """INSERT INTO foundation_lifecycles
                (session_id,lifecycle_id,case_id,candidate_version_id,state,canonical_json,
                canonical_sha256,authority_receipt_json,scan_receipt_json,boundary_receipt_json,
                validation_receipt_json,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    session_id,
                    lifecycle_id,
                    case_id,
                    candidate_version_id_local,
                    KnowledgeState.QUARANTINED.value,
                    canonical_json_bytes(canonical_json).decode("utf-8"),
                    canonical_local.canonical_sha256,
                    canonical_json_bytes(trusted.authority_receipt).decode("utf-8"),
                    canonical_json_bytes(trusted.scan_receipt).decode("utf-8"),
                    canonical_json_bytes(
                        boundary.receipt.model_dump(mode="json")
                    ).decode("utf-8"),
                    canonical_json_bytes(
                        validation_local.model_dump(mode="json")
                    ).decode("utf-8"),
                    timestamp,
                    timestamp,
                ),
            )
            return {
                "contract": "casepath.foundation-live-intake-result/1.0.0",
                "lifecycle_id": lifecycle_id,
                "case_id": case_id,
                "state": KnowledgeState.QUARANTINED.value,
                "candidate_version_id": candidate_version_id_local,
                "canonical": canonical_json,
                "product_projection": canonical_to_product(canonical_local),
                "trusted_privacy_receipt": trusted.authority_receipt,
                "privacy_scan_receipt": trusted.scan_receipt,
                "model_boundary_receipt": boundary.receipt.model_dump(mode="json"),
                "validation_receipt": validation_local.model_dump(mode="json"),
                "initial_knowledge_receipt": initial_receipt,
                "candidate_receipt": candidate_receipt,
                "quarantine_receipt": quarantine_receipt,
                "scientific_nonclaim": (
                    "Deterministic reference execution is infrastructure evidence, "
                    "not model performance or method advantage."
                ),
            }

        response, replayed = self.store.run_idempotent(
            session_id=session_id,
            action="trusted_intake",
            idempotency_key=idempotency_key,
            inputs=inputs,
            timestamp=timestamp,
            operation=operation,
        )
        return {**response, "idempotent_replay": replayed}

    def issue_review_authorization(
        self,
        *,
        session_id: str,
        lifecycle_id: str,
        artifact_version: str,
        accepted_corrections: list[dict[str, Any]],
        idempotency_key: str,
    ) -> dict[str, Any]:
        now = self._clock()
        timestamp = now.isoformat()
        corrections_sha256 = digest_value(accepted_corrections)
        inputs = {
            "lifecycle_id": lifecycle_id,
            "artifact_version": artifact_version,
            "accepted_corrections": accepted_corrections,
        }

        def operation(connection: sqlite3.Connection) -> dict[str, Any]:
            lifecycle = self.store.lifecycle(connection, session_id, lifecycle_id)
            if (
                lifecycle is None
                or lifecycle["state"] != KnowledgeState.QUARANTINED.value
            ):
                raise FoundationLiveError(
                    "review authorization requires quarantined lifecycle"
                )
            if lifecycle["candidate_version_id"] != artifact_version:
                raise FoundationLiveError(
                    "review authorization artifact version mismatch"
                )
            nonce = digest_value(
                {
                    "session_id": session_id,
                    "lifecycle_id": lifecycle_id,
                    "artifact_version": artifact_version,
                    "corrections_sha256": corrections_sha256,
                    "idempotency_key": idempotency_key,
                }
            )
            authorization_payload = {
                "contract": "casepath.non-human-test-review-authorization/1.0.0",
                "authority_type": "non_human_test_fixture",
                "principal_id": TEST_REVIEW_PRINCIPAL_ID,
                "role": TEST_REVIEW_ROLE,
                "session_id": session_id,
                "lifecycle_id": lifecycle_id,
                "reviewed_artifact_version": artifact_version,
                "accepted_corrections": accepted_corrections,
                "corrections_sha256": corrections_sha256,
                "timestamp": timestamp,
                "expires_at": (now + timedelta(minutes=10)).isoformat(),
                "nonce": nonce,
                "provenance_sha256": digest_value(lifecycle["canonical"]["provenance"]),
                "test_trust_root": True,
            }
            signature = _hmac(authorization_payload, self._review_trust_root)
            connection.execute(
                """INSERT INTO foundation_review_nonces
                (session_id,nonce,lifecycle_id,artifact_version,corrections_sha256,
                principal_id,role,issued_at,expires_at,signature,status)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    session_id,
                    nonce,
                    lifecycle_id,
                    artifact_version,
                    corrections_sha256,
                    TEST_REVIEW_PRINCIPAL_ID,
                    TEST_REVIEW_ROLE,
                    timestamp,
                    authorization_payload["expires_at"],
                    signature,
                    "issued",
                ),
            )
            return {
                "authorization": {**authorization_payload, "signature": signature},
                "warning": "non_human_test_fixture; not genuine expert or human review",
            }

        response, replayed = self.store.run_idempotent(
            session_id=session_id,
            action="issue_review_authorization",
            idempotency_key=idempotency_key,
            inputs=inputs,
            timestamp=timestamp,
            operation=operation,
        )
        return {**response, "idempotent_replay": replayed}

    def submit_review(
        self,
        *,
        session_id: str,
        authorization: dict[str, Any],
        idempotency_key: str,
    ) -> dict[str, Any]:
        timestamp = self._timestamp()
        inputs = {"authorization": authorization}

        def operation(connection: sqlite3.Connection) -> dict[str, Any]:
            signature = authorization.get("signature")
            payload = {
                key: value for key, value in authorization.items() if key != "signature"
            }
            if set(authorization) != {
                "contract",
                "authority_type",
                "principal_id",
                "role",
                "session_id",
                "lifecycle_id",
                "reviewed_artifact_version",
                "accepted_corrections",
                "corrections_sha256",
                "timestamp",
                "expires_at",
                "nonce",
                "provenance_sha256",
                "test_trust_root",
                "signature",
            }:
                raise FoundationLiveError("review authorization fields mismatch")
            if not isinstance(signature, str) or not hmac.compare_digest(
                signature, _hmac(payload, self._review_trust_root)
            ):
                raise FoundationLiveError("review authorization signature invalid")
            if authorization["session_id"] != session_id:
                raise FoundationLiveError("review authorization session mismatch")
            if authorization["authority_type"] != "non_human_test_fixture":
                raise FoundationLiveError("review authority type mismatch")
            if authorization["principal_id"] != TEST_REVIEW_PRINCIPAL_ID:
                raise FoundationLiveError("review principal mismatch")
            if authorization["role"] != TEST_REVIEW_ROLE:
                raise FoundationLiveError("review role is not authorized")
            if authorization["principal_id"] in self._revoked_principals:
                raise FoundationLiveError("review principal is revoked")
            if self._clock() > datetime.fromisoformat(str(authorization["expires_at"])):
                raise FoundationLiveError("review authorization expired")
            if (
                digest_value(authorization["accepted_corrections"])
                != authorization["corrections_sha256"]
            ):
                raise FoundationLiveError("review corrections were tampered")
            nonce_row = connection.execute(
                """SELECT * FROM foundation_review_nonces
                WHERE session_id=? AND nonce=?""",
                (session_id, authorization["nonce"]),
            ).fetchone()
            if nonce_row is None:
                raise FoundationLiveError("review nonce is unknown")
            if nonce_row["status"] != "issued":
                raise FoundationLiveError("review authorization replay rejected")
            expected_nonce_values = {
                "lifecycle_id": nonce_row["lifecycle_id"],
                "artifact_version": nonce_row["artifact_version"],
                "corrections_sha256": nonce_row["corrections_sha256"],
                "principal_id": nonce_row["principal_id"],
                "role": nonce_row["role"],
                "signature": nonce_row["signature"],
            }
            observed_nonce_values = {
                "lifecycle_id": authorization["lifecycle_id"],
                "artifact_version": authorization["reviewed_artifact_version"],
                "corrections_sha256": authorization["corrections_sha256"],
                "principal_id": authorization["principal_id"],
                "role": authorization["role"],
                "signature": signature,
            }
            if expected_nonce_values != observed_nonce_values:
                raise FoundationLiveError(
                    "review authorization does not match issued nonce"
                )
            lifecycle = self.store.lifecycle(
                connection, session_id, authorization["lifecycle_id"]
            )
            if (
                lifecycle is None
                or lifecycle["state"] != KnowledgeState.QUARANTINED.value
            ):
                raise FoundationLiveError("reviewed artifact is not quarantined")
            if (
                lifecycle["candidate_version_id"]
                != authorization["reviewed_artifact_version"]
            ):
                raise FoundationLiveError("reviewed artifact version mismatch")
            if (
                digest_value(lifecycle["canonical"]["provenance"])
                != authorization["provenance_sha256"]
            ):
                raise FoundationLiveError("review provenance mismatch")
            version = self.store.version(
                connection, session_id, lifecycle["candidate_version_id"]
            )
            if version is None or version["state"] != KnowledgeState.QUARANTINED.value:
                raise FoundationLiveError("candidate version is not quarantined")
            review_payload = {
                "contract": "casepath.authenticated-review-receipt/1.0.0",
                "reviewer_authority_type": "non_human_test_fixture",
                "principal_id": authorization["principal_id"],
                "role": authorization["role"],
                "reviewed_artifact_version": authorization["reviewed_artifact_version"],
                "accepted_corrections": authorization["accepted_corrections"],
                "timestamp": authorization["timestamp"],
                "nonce": authorization["nonce"],
                "provenance": lifecycle["canonical"]["provenance"],
                "authorization_payload_sha256": digest_value(payload),
                "authorization_signature": signature,
                "signature_verified": True,
                "role_verified": True,
                "revocation_checked": True,
                "replay_checked": True,
                "artifact_version_verified": True,
                "human_or_expert_review": False,
            }
            review_receipt = {
                **review_payload,
                "receipt_sha256": digest_value(review_payload),
            }
            connection.execute(
                """UPDATE foundation_review_nonces SET status='consumed'
                WHERE session_id=? AND nonce=? AND status='issued'""",
                (session_id, authorization["nonce"]),
            )
            if connection.total_changes < 1:
                raise FoundationLiveError("review authorization replay rejected")
            connection.execute(
                """UPDATE foundation_versions
                SET state=?,review_receipt_json=?,updated_at=?
                WHERE session_id=? AND version_id=? AND state=?""",
                (
                    KnowledgeState.REVIEWED.value,
                    canonical_json_bytes(review_receipt).decode("utf-8"),
                    timestamp,
                    session_id,
                    version["version_id"],
                    KnowledgeState.QUARANTINED.value,
                ),
            )
            connection.execute(
                """UPDATE foundation_lifecycles SET state=?,updated_at=?
                WHERE session_id=? AND lifecycle_id=? AND state=?""",
                (
                    KnowledgeState.REVIEWED.value,
                    timestamp,
                    session_id,
                    lifecycle["lifecycle_id"],
                    KnowledgeState.QUARANTINED.value,
                ),
            )
            session = self.store.session(connection, session_id)
            transition = _receipt(
                action="record_authenticated_review",
                version_id=version["version_id"],
                state_before=KnowledgeState.QUARANTINED.value,
                state_after=KnowledgeState.REVIEWED.value,
                active_before=session["active_version_id"] if session else None,
                active_after=session["active_version_id"] if session else None,
                rollback_target=version["rollback_target"],
                content_sha256=version["content_sha256"],
                provenance=version["provenance"],
                timestamp=timestamp,
            )
            _record_history(
                connection,
                session_id=session_id,
                lifecycle_id=lifecycle["lifecycle_id"],
                receipt=transition,
            )
            return {
                "state": KnowledgeState.REVIEWED.value,
                "review_receipt": review_receipt,
                "governance_receipt": transition,
                "warning": "non_human_test_fixture; not genuine expert or human review",
            }

        response, replayed = self.store.run_idempotent(
            session_id=session_id,
            action="submit_authenticated_review",
            idempotency_key=idempotency_key,
            inputs=inputs,
            timestamp=timestamp,
            operation=operation,
        )
        return {**response, "idempotent_replay": replayed}

    def regression(
        self, *, session_id: str, lifecycle_id: str, idempotency_key: str
    ) -> dict[str, Any]:
        timestamp = self._timestamp()
        inputs = {"lifecycle_id": lifecycle_id}

        def operation(connection: sqlite3.Connection) -> dict[str, Any]:
            lifecycle = self.store.lifecycle(connection, session_id, lifecycle_id)
            if lifecycle is None or lifecycle["state"] != KnowledgeState.REVIEWED.value:
                raise FoundationLiveError("regression requires reviewed lifecycle")
            version = self.store.version(
                connection, session_id, lifecycle["candidate_version_id"]
            )
            if version is None or version["review_receipt"] is None:
                raise FoundationLiveError(
                    "regression requires authenticated review receipt"
                )
            checks = [
                {
                    "check": "canonical_validation_passed",
                    "passed": lifecycle["validation_receipt"]["passed"] is True,
                },
                {
                    "check": "content_address_valid",
                    "passed": digest_value(version["content"])
                    == version["content_sha256"],
                },
                {
                    "check": "provenance_preserved",
                    "passed": version["provenance"]
                    == lifecycle["canonical"]["provenance"],
                },
                {
                    "check": "authenticated_non_human_fixture_review",
                    "passed": version["review_receipt"]["signature_verified"] is True,
                },
            ]
            passed = all(check["passed"] for check in checks)
            regression_payload = {
                "contract": "casepath.live-regression-receipt/1.0.0",
                "artifact_version": version["version_id"],
                "test_manifest_sha256": digest_value(checks),
                "passed": passed,
                "checks": checks,
                "timestamp": timestamp,
                "provenance": version["provenance"],
            }
            regression_receipt = {
                **regression_payload,
                "receipt_sha256": digest_value(regression_payload),
            }
            if not passed:
                raise FoundationLiveError("regression gate failed")
            connection.execute(
                """UPDATE foundation_versions
                SET state=?,regression_receipt_json=?,updated_at=?
                WHERE session_id=? AND version_id=? AND state=?""",
                (
                    KnowledgeState.REGRESSION_PASSED.value,
                    canonical_json_bytes(regression_receipt).decode("utf-8"),
                    timestamp,
                    session_id,
                    version["version_id"],
                    KnowledgeState.REVIEWED.value,
                ),
            )
            connection.execute(
                """UPDATE foundation_lifecycles SET state=?,updated_at=?
                WHERE session_id=? AND lifecycle_id=? AND state=?""",
                (
                    KnowledgeState.REGRESSION_PASSED.value,
                    timestamp,
                    session_id,
                    lifecycle_id,
                    KnowledgeState.REVIEWED.value,
                ),
            )
            session = self.store.session(connection, session_id)
            transition = _receipt(
                action="record_regression",
                version_id=version["version_id"],
                state_before=KnowledgeState.REVIEWED.value,
                state_after=KnowledgeState.REGRESSION_PASSED.value,
                active_before=session["active_version_id"] if session else None,
                active_after=session["active_version_id"] if session else None,
                rollback_target=version["rollback_target"],
                content_sha256=version["content_sha256"],
                provenance=version["provenance"],
                timestamp=timestamp,
            )
            _record_history(
                connection,
                session_id=session_id,
                lifecycle_id=lifecycle_id,
                receipt=transition,
            )
            return {
                "state": KnowledgeState.REGRESSION_PASSED.value,
                "regression_receipt": regression_receipt,
                "governance_receipt": transition,
            }

        response, replayed = self.store.run_idempotent(
            session_id=session_id,
            action="regression_gate",
            idempotency_key=idempotency_key,
            inputs=inputs,
            timestamp=timestamp,
            operation=operation,
        )
        return {**response, "idempotent_replay": replayed}

    def promote(
        self, *, session_id: str, lifecycle_id: str, idempotency_key: str
    ) -> dict[str, Any]:
        timestamp = self._timestamp()
        inputs = {"lifecycle_id": lifecycle_id}

        def operation(connection: sqlite3.Connection) -> dict[str, Any]:
            lifecycle = self.store.lifecycle(connection, session_id, lifecycle_id)
            if (
                lifecycle is None
                or lifecycle["state"] != KnowledgeState.REGRESSION_PASSED.value
            ):
                raise FoundationLiveError(
                    "promotion requires regression_passed lifecycle"
                )
            version = self.store.version(
                connection, session_id, lifecycle["candidate_version_id"]
            )
            session = self.store.session(connection, session_id)
            if version is None or session is None:
                raise FoundationLiveError("promotion state is missing")
            if (
                version["review_receipt"] is None
                or version["regression_receipt"] is None
            ):
                raise FoundationLiveError(
                    "promotion requires review and regression receipts"
                )
            if version["review_receipt"].get("signature_verified") is not True:
                raise FoundationLiveError("promotion review signature is not verified")
            if version["regression_receipt"].get("passed") is not True:
                raise FoundationLiveError("promotion regression did not pass")
            if version["rollback_target"] != session["active_version_id"]:
                raise FoundationLiveError(
                    "promotion rollback target is not the active version"
                )
            prior = self.store.version(
                connection, session_id, version["rollback_target"]
            )
            if prior is None or prior["state"] != KnowledgeState.PROMOTED.value:
                raise FoundationLiveError("promotion rollback target is not promoted")
            if (
                content_address("knowledge", version["content"])
                != version["version_id"]
            ):
                raise FoundationLiveError("candidate content address mismatch")
            prior_snapshot = version["content"].get("rollback_snapshot")
            if prior_snapshot != session["active_snapshot"]:
                raise FoundationLiveError("promotion rollback snapshot mismatch")
            connection.execute(
                """UPDATE foundation_versions SET state=?,updated_at=?
                WHERE session_id=? AND version_id=? AND state=?""",
                (
                    KnowledgeState.SUPERSEDED.value,
                    timestamp,
                    session_id,
                    prior["version_id"],
                    KnowledgeState.PROMOTED.value,
                ),
            )
            supersede_receipt = _receipt(
                action="supersede",
                version_id=prior["version_id"],
                state_before=KnowledgeState.PROMOTED.value,
                state_after=KnowledgeState.SUPERSEDED.value,
                active_before=prior["version_id"],
                active_after=version["version_id"],
                rollback_target=prior["rollback_target"],
                content_sha256=prior["content_sha256"],
                provenance=prior["provenance"],
                timestamp=timestamp,
            )
            _record_history(
                connection,
                session_id=session_id,
                lifecycle_id=prior["lifecycle_id"],
                receipt=supersede_receipt,
            )
            connection.execute(
                """UPDATE foundation_versions SET state=?,updated_at=?
                WHERE session_id=? AND version_id=? AND state=?""",
                (
                    KnowledgeState.PROMOTED.value,
                    timestamp,
                    session_id,
                    version["version_id"],
                    KnowledgeState.REGRESSION_PASSED.value,
                ),
            )
            index_sha256 = digest_value(
                {
                    "version_id": version["version_id"],
                    "case_ids": [lifecycle["case_id"]],
                }
            )
            active_snapshot = {
                "version_id": version["version_id"],
                "content": version["content"],
                "content_sha256": version["content_sha256"],
                "provenance": version["provenance"],
                "index_sha256": index_sha256,
            }
            connection.execute(
                """UPDATE foundation_sessions
                SET active_version_id=?,active_snapshot_json=?,active_index_sha256=?,updated_at=?
                WHERE session_id=?""",
                (
                    version["version_id"],
                    canonical_json_bytes(active_snapshot).decode("utf-8"),
                    index_sha256,
                    timestamp,
                    session_id,
                ),
            )
            connection.execute(
                """UPDATE foundation_lifecycles SET state=?,updated_at=?
                WHERE session_id=? AND lifecycle_id=? AND state=?""",
                (
                    KnowledgeState.PROMOTED.value,
                    timestamp,
                    session_id,
                    lifecycle_id,
                    KnowledgeState.REGRESSION_PASSED.value,
                ),
            )
            promotion_receipt = _receipt(
                action="promote",
                version_id=version["version_id"],
                state_before=KnowledgeState.REGRESSION_PASSED.value,
                state_after=KnowledgeState.PROMOTED.value,
                active_before=prior["version_id"],
                active_after=version["version_id"],
                rollback_target=prior["version_id"],
                content_sha256=version["content_sha256"],
                provenance=version["provenance"],
                timestamp=timestamp,
            )
            _record_history(
                connection,
                session_id=session_id,
                lifecycle_id=lifecycle_id,
                receipt=promotion_receipt,
            )
            return {
                "state": KnowledgeState.PROMOTED.value,
                "active_version_id": version["version_id"],
                "active_index_sha256": index_sha256,
                "supersede_receipt": supersede_receipt,
                "promotion_receipt": promotion_receipt,
            }

        response, replayed = self.store.run_idempotent(
            session_id=session_id,
            action="promote",
            idempotency_key=idempotency_key,
            inputs=inputs,
            timestamp=timestamp,
            operation=operation,
        )
        return {**response, "idempotent_replay": replayed}

    def retrieve(
        self,
        *,
        session_id: str,
        later_case_id: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        timestamp = self._timestamp()
        # Admission is a server-side identity check; the result is not executed.
        self.registry.admit(later_case_id)
        inputs = {"later_case_id": later_case_id}

        def operation(connection: sqlite3.Connection) -> dict[str, Any]:
            session = self.store.session(connection, session_id)
            if session is None or session["active_version_id"] is None:
                raise FoundationLiveError("no active knowledge to retrieve")
            version = self.store.version(
                connection, session_id, session["active_version_id"]
            )
            if version is None or version["state"] != KnowledgeState.PROMOTED.value:
                raise FoundationLiveError("active knowledge is not promoted")
            payload = {
                "contract": "casepath.persistent-knowledge-retrieval-receipt/1.0.0",
                "later_case_id": later_case_id,
                "active_version_id": version["version_id"],
                "content_sha256": version["content_sha256"],
                "provenance": version["provenance"],
                "active_index_sha256": session["active_index_sha256"],
                "timestamp": timestamp,
                "model_calls": 0,
                "provider_calls": 0,
                "cost_usd": 0.0,
            }
            receipt = {**payload, "receipt_sha256": digest_value(payload)}
            return {"knowledge": version["content"], "retrieval_receipt": receipt}

        response, replayed = self.store.run_idempotent(
            session_id=session_id,
            action="retrieve_later_case",
            idempotency_key=idempotency_key,
            inputs=inputs,
            timestamp=timestamp,
            operation=operation,
        )
        return {**response, "idempotent_replay": replayed}

    def rollback(
        self, *, session_id: str, lifecycle_id: str, idempotency_key: str
    ) -> dict[str, Any]:
        timestamp = self._timestamp()
        inputs = {"lifecycle_id": lifecycle_id}

        def operation(connection: sqlite3.Connection) -> dict[str, Any]:
            lifecycle = self.store.lifecycle(connection, session_id, lifecycle_id)
            session = self.store.session(connection, session_id)
            if lifecycle is None or session is None:
                raise FoundationLiveError("rollback state is missing")
            current = self.store.version(
                connection, session_id, session["active_version_id"]
            )
            if (
                current is None
                or current["version_id"] != lifecycle["candidate_version_id"]
            ):
                raise FoundationLiveError("rollback lifecycle is not active")
            if current["state"] != KnowledgeState.PROMOTED.value:
                raise FoundationLiveError("rollback requires promoted active knowledge")
            target = self.store.version(
                connection, session_id, current["rollback_target"]
            )
            if target is None or target["state"] != KnowledgeState.SUPERSEDED.value:
                raise FoundationLiveError("rollback target is not superseded")
            expected_snapshot = current["content"].get("rollback_snapshot")
            target_index = (
                expected_snapshot.get("index_sha256")
                if isinstance(expected_snapshot, dict)
                else None
            )
            restored_snapshot = {
                "version_id": target["version_id"],
                "content": target["content"],
                "content_sha256": target["content_sha256"],
                "provenance": target["provenance"],
                "index_sha256": target_index,
            }
            exact = restored_snapshot == expected_snapshot
            if not exact:
                raise FoundationLiveError("rollback snapshot is not exact")
            connection.execute(
                """UPDATE foundation_versions SET state=?,updated_at=?
                WHERE session_id=? AND version_id=? AND state=?""",
                (
                    KnowledgeState.ROLLED_BACK.value,
                    timestamp,
                    session_id,
                    current["version_id"],
                    KnowledgeState.PROMOTED.value,
                ),
            )
            connection.execute(
                """UPDATE foundation_versions SET state=?,updated_at=?
                WHERE session_id=? AND version_id=? AND state=?""",
                (
                    KnowledgeState.PROMOTED.value,
                    timestamp,
                    session_id,
                    target["version_id"],
                    KnowledgeState.SUPERSEDED.value,
                ),
            )
            connection.execute(
                """UPDATE foundation_sessions SET active_version_id=?,active_snapshot_json=?,
                active_index_sha256=?,updated_at=? WHERE session_id=?""",
                (
                    target["version_id"],
                    canonical_json_bytes(restored_snapshot).decode("utf-8"),
                    target_index,
                    timestamp,
                    session_id,
                ),
            )
            connection.execute(
                """UPDATE foundation_lifecycles SET state=?,updated_at=?
                WHERE session_id=? AND lifecycle_id=?""",
                (
                    KnowledgeState.ROLLED_BACK.value,
                    timestamp,
                    session_id,
                    lifecycle_id,
                ),
            )
            rollback_receipt = _receipt(
                action="rollback",
                version_id=current["version_id"],
                state_before=KnowledgeState.PROMOTED.value,
                state_after=KnowledgeState.ROLLED_BACK.value,
                active_before=current["version_id"],
                active_after=target["version_id"],
                rollback_target=target["version_id"],
                content_sha256=current["content_sha256"],
                provenance=current["provenance"],
                timestamp=timestamp,
                exact_prior_version_restored=True,
            )
            _record_history(
                connection,
                session_id=session_id,
                lifecycle_id=lifecycle_id,
                receipt=rollback_receipt,
            )
            restore_receipt = _receipt(
                action="restore_prior",
                version_id=target["version_id"],
                state_before=KnowledgeState.SUPERSEDED.value,
                state_after=KnowledgeState.PROMOTED.value,
                active_before=current["version_id"],
                active_after=target["version_id"],
                rollback_target=target["rollback_target"],
                content_sha256=target["content_sha256"],
                provenance=target["provenance"],
                timestamp=timestamp,
                exact_prior_version_restored=True,
            )
            _record_history(
                connection,
                session_id=session_id,
                lifecycle_id=target["lifecycle_id"],
                receipt=restore_receipt,
            )
            return {
                "state": KnowledgeState.ROLLED_BACK.value,
                "active_version_id": target["version_id"],
                "active_snapshot": restored_snapshot,
                "exact_prior_version_restored": True,
                "rollback_receipt": rollback_receipt,
                "restore_receipt": restore_receipt,
            }

        response, replayed = self.store.run_idempotent(
            session_id=session_id,
            action="rollback",
            idempotency_key=idempotency_key,
            inputs=inputs,
            timestamp=timestamp,
            operation=operation,
        )
        return {**response, "idempotent_replay": replayed}

    def state(self, *, session_id: str, lifecycle_id: str) -> dict[str, Any]:
        lifecycle = self.store.read_lifecycle(session_id, lifecycle_id)
        session = self.store.read_session(session_id)
        if lifecycle is None or session is None:
            raise FoundationLiveError("foundation lifecycle not found")
        payload = {
            "contract": "casepath.foundation-live-state/1.0.0",
            "lifecycle": lifecycle,
            "session": session,
            "restart_recovered": True,
        }
        return {**payload, "receipt_sha256": digest_value(payload)}

    def benchmark_projection(
        self, *, session_id: str, lifecycle_id: str
    ) -> dict[str, Any]:
        lifecycle = self.store.read_lifecycle(session_id, lifecycle_id)
        if lifecycle is None:
            raise FoundationLiveError("foundation lifecycle not found")
        canonical = CanonicalCaseArtifact.model_validate(lifecycle["canonical"])
        projection = canonical_to_benchmark(canonical)
        payload = {
            "contract": "casepath.foundation-live-benchmark-result/1.0.0",
            "lifecycle_id": lifecycle_id,
            "projection": projection,
            "projection_sha256": digest_value(projection),
            "central_hypothesis": "UNTESTED",
            "interpretation": (
                "A deterministic reference projection verifies integration only; "
                "it is not model or method performance."
            ),
        }
        return {**payload, "receipt_sha256": digest_value(payload)}

    def audit_export(self, *, session_id: str) -> dict[str, Any]:
        export = self.store.audit_export(session_id)
        payload = {
            **export,
            "compatibility": self.compatibility(),
            "execution": {
                "model_calls": 0,
                "provider_calls": 0,
                "provider_credentials_read": False,
                "cost_usd": 0.0,
                "sealed_data_accessed": False,
                "human_or_expert_study": False,
            },
        }
        unsigned = {
            key: value for key, value in payload.items() if key != "receipt_sha256"
        }
        return {**unsigned, "receipt_sha256": digest_value(unsigned)}

    def record_ui_trace(
        self,
        *,
        session_id: str,
        lifecycle_id: str,
        trace: dict[str, Any],
        idempotency_key: str,
    ) -> dict[str, Any]:
        timestamp = self._timestamp()
        inputs = {"lifecycle_id": lifecycle_id, "trace": trace}

        def operation(connection: sqlite3.Connection) -> dict[str, Any]:
            lifecycle = self.store.lifecycle(connection, session_id, lifecycle_id)
            if lifecycle is None:
                raise FoundationLiveError("UI trace lifecycle not found")
            if trace.get("contract") != "casepath.foundation-ui-api-trace/1.0.0":
                raise FoundationLiveError("UI trace contract mismatch")
            if (
                trace.get("session_id") != session_id
                or trace.get("lifecycle_id") != lifecycle_id
            ):
                raise FoundationLiveError("UI trace identity mismatch")
            if trace.get("model_calls") != 0 or trace.get("provider_calls") != 0:
                raise FoundationLiveError(
                    "UI trace reports a forbidden model/provider call"
                )
            calls = trace.get("calls")
            if not isinstance(calls, list) or not calls:
                raise FoundationLiveError("UI trace has no API calls")
            permitted_prefix = "/api/foundation/v1/"
            if any(
                not isinstance(call, dict)
                or not str(call.get("path", "")).startswith(permitted_prefix)
                for call in calls
            ):
                raise FoundationLiveError("UI trace contains a non-foundation API path")
            trace_sha256 = digest_value(trace)
            trace_id = f"ui-trace.{trace_sha256}"
            connection.execute(
                """INSERT INTO foundation_ui_traces
                (session_id,trace_id,lifecycle_id,trace_json,trace_sha256,created_at)
                VALUES (?,?,?,?,?,?)""",
                (
                    session_id,
                    trace_id,
                    lifecycle_id,
                    canonical_json_bytes(trace).decode("utf-8"),
                    trace_sha256,
                    timestamp,
                ),
            )
            receipt_payload = {
                "contract": "casepath.foundation-ui-trace-receipt/1.0.0",
                "trace_id": trace_id,
                "lifecycle_id": lifecycle_id,
                "trace_sha256": trace_sha256,
                "call_count": len(calls),
                "timestamp": timestamp,
            }
            return {
                "trace_receipt": {
                    **receipt_payload,
                    "receipt_sha256": digest_value(receipt_payload),
                }
            }

        response, replayed = self.store.run_idempotent(
            session_id=session_id,
            action="record_ui_trace",
            idempotency_key=idempotency_key,
            inputs=inputs,
            timestamp=timestamp,
            operation=operation,
        )
        return {**response, "idempotent_replay": replayed}


def translate_persistence_error(exc: Exception) -> FoundationLiveError:
    if isinstance(exc, FoundationLiveError):
        return exc
    if isinstance(exc, FoundationPersistenceError):
        return FoundationLiveError(str(exc))
    return FoundationLiveError("foundation persistence operation failed")
