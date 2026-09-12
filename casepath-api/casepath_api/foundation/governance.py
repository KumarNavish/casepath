from __future__ import annotations

from copy import deepcopy
from typing import Any

from .common import content_address, digest_value
from .contracts import (
    GovernanceReceipt,
    KnowledgeState,
    KnowledgeVersion,
    RegressionReceipt,
    RetrievalReceipt,
    ReviewReceipt,
    ReviewerAuthorityType,
    SourceLocator,
)


class KnowledgeGovernanceError(RuntimeError):
    pass


def create_review_receipt(
    *,
    reviewer_authority_type: ReviewerAuthorityType,
    reviewed_artifact_version: str,
    accepted_corrections: tuple[dict[str, Any], ...],
    timestamp: str,
    provenance: tuple[SourceLocator, ...],
) -> ReviewReceipt:
    payload = {
        "contract": "casepath.review-receipt/1.0.0",
        "reviewer_authority_type": reviewer_authority_type.value,
        "reviewed_artifact_version": reviewed_artifact_version,
        "accepted_corrections": list(accepted_corrections),
        "timestamp": timestamp,
        "provenance": [value.model_dump(mode="json") for value in provenance],
    }
    return ReviewReceipt.model_validate(
        {**payload, "signature_or_integrity_sha256": digest_value(payload)}
    )


def create_regression_receipt(
    *,
    artifact_version: str,
    test_manifest_sha256: str,
    passed: bool,
    timestamp: str,
    provenance: tuple[SourceLocator, ...],
) -> RegressionReceipt:
    payload = {
        "contract": "casepath.regression-receipt/1.0.0",
        "artifact_version": artifact_version,
        "test_manifest_sha256": test_manifest_sha256,
        "passed": passed,
        "timestamp": timestamp,
        "provenance": [value.model_dump(mode="json") for value in provenance],
    }
    return RegressionReceipt.model_validate(
        {**payload, "integrity_sha256": digest_value(payload)}
    )


def _review_is_valid(receipt: ReviewReceipt) -> bool:
    payload = receipt.model_dump(mode="json", exclude={"signature_or_integrity_sha256"})
    return digest_value(payload) == receipt.signature_or_integrity_sha256


def _regression_is_valid(receipt: RegressionReceipt) -> bool:
    payload = receipt.model_dump(mode="json", exclude={"integrity_sha256"})
    return digest_value(payload) == receipt.integrity_sha256


class KnowledgeGovernance:
    """In-memory deterministic governance state machine with hash-bound receipts.

    The `non_human_test_fixture` authority is accepted only when fixture mode is
    explicitly enabled. It never represents qualified review.
    """

    def __init__(self, *, allow_non_human_test_fixture: bool = False) -> None:
        self.allow_non_human_test_fixture = allow_non_human_test_fixture
        self._versions: dict[str, KnowledgeVersion] = {}
        self._active_version_id: str | None = None
        self._receipts: list[GovernanceReceipt | RetrievalReceipt] = []

    @property
    def active_version_id(self) -> str | None:
        return self._active_version_id

    def versions(self) -> tuple[KnowledgeVersion, ...]:
        return tuple(
            self._versions[key].model_copy(deep=True) for key in sorted(self._versions)
        )

    def receipts(self) -> tuple[GovernanceReceipt | RetrievalReceipt, ...]:
        return tuple(value.model_copy(deep=True) for value in self._receipts)

    def _new_governance_receipt(
        self,
        *,
        action: str,
        version: KnowledgeVersion,
        state_before: KnowledgeState | None,
        state_after: KnowledgeState,
        active_before: str | None,
        active_after: str | None,
        timestamp: str,
        exact_prior_version_restored: bool | None = None,
    ) -> GovernanceReceipt:
        payload = {
            "contract": "casepath.knowledge-governance-receipt/1.0.0",
            "action": action,
            "version_id": version.version_id,
            "state_before": state_before.value if state_before else None,
            "state_after": state_after.value,
            "active_before": active_before,
            "active_after": active_after,
            "rollback_target": version.rollback_target,
            "content_sha256": version.content_sha256,
            "provenance": [
                value.model_dump(mode="json") for value in version.provenance
            ],
            "exact_prior_version_restored": exact_prior_version_restored,
            "timestamp": timestamp,
        }
        receipt = GovernanceReceipt.model_validate(
            {**payload, "receipt_sha256": digest_value(payload)}
        )
        self._receipts.append(receipt)
        return receipt

    def install_initial(
        self,
        *,
        content: dict[str, Any],
        provenance: tuple[SourceLocator, ...],
        timestamp: str,
    ) -> GovernanceReceipt:
        if self._active_version_id is not None or self._versions:
            raise KnowledgeGovernanceError("initial knowledge already installed")
        frozen_content = deepcopy(content)
        content_sha256 = digest_value(frozen_content)
        version = KnowledgeVersion(
            version_id=content_address("knowledge", frozen_content),
            content_sha256=content_sha256,
            content=frozen_content,
            state=KnowledgeState.PROMOTED,
            rollback_target=None,
            provenance=provenance,
        )
        self._versions[version.version_id] = version
        self._active_version_id = version.version_id
        return self._new_governance_receipt(
            action="install_initial",
            version=version,
            state_before=None,
            state_after=KnowledgeState.PROMOTED,
            active_before=None,
            active_after=version.version_id,
            timestamp=timestamp,
        )

    def create_candidate(
        self,
        *,
        content: dict[str, Any],
        provenance: tuple[SourceLocator, ...],
        timestamp: str,
    ) -> GovernanceReceipt:
        if self._active_version_id is None:
            raise KnowledgeGovernanceError("an active rollback target is required")
        frozen_content = deepcopy(content)
        version_id = content_address("knowledge", frozen_content)
        if version_id in self._versions:
            raise KnowledgeGovernanceError("content-addressed version already exists")
        version = KnowledgeVersion(
            version_id=version_id,
            content_sha256=digest_value(frozen_content),
            content=frozen_content,
            state=KnowledgeState.CANDIDATE,
            rollback_target=self._active_version_id,
            provenance=provenance,
        )
        self._versions[version_id] = version
        return self._new_governance_receipt(
            action="create_candidate",
            version=version,
            state_before=None,
            state_after=KnowledgeState.CANDIDATE,
            active_before=self._active_version_id,
            active_after=self._active_version_id,
            timestamp=timestamp,
        )

    def _transition(
        self,
        version_id: str,
        *,
        expected: KnowledgeState,
        target: KnowledgeState,
        action: str,
        timestamp: str,
        review_receipt: ReviewReceipt | None = None,
        regression_receipt: RegressionReceipt | None = None,
    ) -> GovernanceReceipt:
        version = self._versions.get(version_id)
        if version is None:
            raise KnowledgeGovernanceError("unknown knowledge version")
        if version.state != expected:
            raise KnowledgeGovernanceError(
                f"{action} requires {expected.value}; found {version.state.value}"
            )
        updated = version.model_copy(
            update={
                "state": target,
                "review_receipt": review_receipt or version.review_receipt,
                "regression_receipt": regression_receipt or version.regression_receipt,
            }
        )
        self._versions[version_id] = updated
        return self._new_governance_receipt(
            action=action,
            version=updated,
            state_before=expected,
            state_after=target,
            active_before=self._active_version_id,
            active_after=self._active_version_id,
            timestamp=timestamp,
        )

    def quarantine(self, version_id: str, *, timestamp: str) -> GovernanceReceipt:
        return self._transition(
            version_id,
            expected=KnowledgeState.CANDIDATE,
            target=KnowledgeState.QUARANTINED,
            action="quarantine",
            timestamp=timestamp,
        )

    def record_review(
        self, version_id: str, receipt: ReviewReceipt, *, timestamp: str
    ) -> GovernanceReceipt:
        if not _review_is_valid(receipt):
            raise KnowledgeGovernanceError("review receipt integrity check failed")
        if receipt.reviewed_artifact_version != version_id:
            raise KnowledgeGovernanceError("review receipt version mismatch")
        if (
            receipt.reviewer_authority_type
            == ReviewerAuthorityType.NON_HUMAN_TEST_FIXTURE
            and not self.allow_non_human_test_fixture
        ):
            raise KnowledgeGovernanceError(
                "non_human_test_fixture review requires explicit fixture mode"
            )
        version = self._versions.get(version_id)
        if version is None or receipt.provenance != version.provenance:
            raise KnowledgeGovernanceError("review provenance mismatch")
        return self._transition(
            version_id,
            expected=KnowledgeState.QUARANTINED,
            target=KnowledgeState.REVIEWED,
            action="record_review",
            timestamp=timestamp,
            review_receipt=receipt,
        )

    def record_regression(
        self, version_id: str, receipt: RegressionReceipt, *, timestamp: str
    ) -> GovernanceReceipt:
        if not _regression_is_valid(receipt):
            raise KnowledgeGovernanceError("regression receipt integrity check failed")
        if receipt.artifact_version != version_id:
            raise KnowledgeGovernanceError("regression receipt version mismatch")
        if receipt.passed is not True:
            raise KnowledgeGovernanceError("regression receipt did not pass")
        version = self._versions.get(version_id)
        if version is None or receipt.provenance != version.provenance:
            raise KnowledgeGovernanceError("regression provenance mismatch")
        return self._transition(
            version_id,
            expected=KnowledgeState.REVIEWED,
            target=KnowledgeState.REGRESSION_PASSED,
            action="record_regression",
            timestamp=timestamp,
            regression_receipt=receipt,
        )

    def promote(self, version_id: str, *, timestamp: str) -> GovernanceReceipt:
        version = self._versions.get(version_id)
        if version is None:
            raise KnowledgeGovernanceError("unknown knowledge version")
        if version.state != KnowledgeState.REGRESSION_PASSED:
            raise KnowledgeGovernanceError("promotion requires regression_passed state")
        if version.review_receipt is None or version.regression_receipt is None:
            raise KnowledgeGovernanceError(
                "promotion requires review and regression receipts"
            )
        if (
            version.rollback_target is None
            or version.rollback_target != self._active_version_id
        ):
            raise KnowledgeGovernanceError(
                "promotion requires the exact active rollback target"
            )
        if version.version_id != content_address("knowledge", version.content):
            raise KnowledgeGovernanceError("knowledge version is not content-addressed")
        previous = self._versions.get(version.rollback_target)
        if previous is None or previous.state != KnowledgeState.PROMOTED:
            raise KnowledgeGovernanceError(
                "rollback target is not the active promoted version"
            )

        active_before = self._active_version_id
        self._versions[previous.version_id] = previous.model_copy(
            update={"state": KnowledgeState.SUPERSEDED}
        )
        promoted = version.model_copy(update={"state": KnowledgeState.PROMOTED})
        self._versions[version_id] = promoted
        self._active_version_id = version_id
        return self._new_governance_receipt(
            action="promote",
            version=promoted,
            state_before=KnowledgeState.REGRESSION_PASSED,
            state_after=KnowledgeState.PROMOTED,
            active_before=active_before,
            active_after=version_id,
            timestamp=timestamp,
        )

    def retrieve(self, *, case_id: str, timestamp: str) -> RetrievalReceipt:
        if self._active_version_id is None:
            raise KnowledgeGovernanceError("no active knowledge version")
        active = self._versions[self._active_version_id]
        if active.state != KnowledgeState.PROMOTED:
            raise KnowledgeGovernanceError("active knowledge is not promoted")
        payload = {
            "contract": "casepath.knowledge-retrieval-receipt/1.0.0",
            "case_id": case_id,
            "active_version_id": active.version_id,
            "content_sha256": active.content_sha256,
            "provenance": [
                value.model_dump(mode="json") for value in active.provenance
            ],
            "timestamp": timestamp,
        }
        receipt = RetrievalReceipt.model_validate(
            {**payload, "receipt_sha256": digest_value(payload)}
        )
        self._receipts.append(receipt)
        return receipt

    def rollback(self, *, timestamp: str) -> GovernanceReceipt:
        if self._active_version_id is None:
            raise KnowledgeGovernanceError("no active knowledge version")
        current = self._versions[self._active_version_id]
        target_id = current.rollback_target
        if current.state != KnowledgeState.PROMOTED or target_id is None:
            raise KnowledgeGovernanceError("active version has no rollback target")
        target = self._versions.get(target_id)
        if target is None or target.state != KnowledgeState.SUPERSEDED:
            raise KnowledgeGovernanceError("rollback target is not superseded")
        if target.version_id != content_address("knowledge", target.content):
            raise KnowledgeGovernanceError("rollback target content address is invalid")

        active_before = current.version_id
        rolled_back = current.model_copy(update={"state": KnowledgeState.ROLLED_BACK})
        restored = target.model_copy(update={"state": KnowledgeState.PROMOTED})
        self._versions[current.version_id] = rolled_back
        self._versions[target.version_id] = restored
        self._active_version_id = target.version_id
        return self._new_governance_receipt(
            action="rollback",
            version=rolled_back,
            state_before=KnowledgeState.PROMOTED,
            state_after=KnowledgeState.ROLLED_BACK,
            active_before=active_before,
            active_after=target.version_id,
            timestamp=timestamp,
            exact_prior_version_restored=(
                restored.version_id == target_id
                and restored.content_sha256 == digest_value(restored.content)
            ),
        )
