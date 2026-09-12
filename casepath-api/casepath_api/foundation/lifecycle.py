from __future__ import annotations

from typing import Any

from .case_adapter import assemble_canonical_artifact, canonical_input_from_privacy
from .common import digest_value
from .contracts import (
    PrivacyIntake,
    ReviewerAuthorityType,
    SourceLocator,
)
from .governance import (
    KnowledgeGovernance,
    create_regression_receipt,
    create_review_receipt,
)
from .model_boundary import ProviderNeutralModel, execute_model_boundary
from .privacy import privacy_gate
from .validation import validate_canonical_artifact


def _knowledge_content(
    *,
    canonical_sha256: str,
    process_artifact: dict[str, Any],
    evidence_document_plan: tuple[dict[str, Any], ...],
) -> dict[str, Any]:
    return {
        "canonical_sha256": canonical_sha256,
        "process_artifact": process_artifact,
        "evidence_document_plan": list(evidence_document_plan),
    }


def execute_foundation_lifecycle(
    *,
    intake: PrivacyIntake,
    adapter: ProviderNeutralModel,
    initial_knowledge_content: dict[str, Any],
    initial_knowledge_provenance: tuple[SourceLocator, ...],
    accepted_corrections: tuple[dict[str, Any], ...],
    regression_test_manifest_sha256: str,
    later_case_id: str,
    timestamp: str,
) -> dict[str, Any]:
    """Execute the bounded deterministic foundation lifecycle.

    The function deliberately requires an injected provider-neutral adapter. The
    authorized proof uses only deterministic reference fixtures, and the review is
    explicitly recorded as ``non_human_test_fixture``.
    """

    privacy_result = privacy_gate(intake)
    case_input = canonical_input_from_privacy(intake, privacy_result)
    boundary_result = execute_model_boundary(adapter, case_input)
    canonical = assemble_canonical_artifact(
        case_input,
        boundary_result.artifact,
        model_boundary_receipt_sha256=boundary_result.receipt.receipt_sha256,
    )
    validation = validate_canonical_artifact(canonical)
    if not validation.passed:
        raise ValueError("canonical artifact failed deterministic validation")

    governance = KnowledgeGovernance(allow_non_human_test_fixture=True)
    initial_receipt = governance.install_initial(
        content=initial_knowledge_content,
        provenance=initial_knowledge_provenance,
        timestamp=timestamp,
    )
    prior_version_id = governance.active_version_id
    if prior_version_id is None:
        raise RuntimeError("initial knowledge installation did not activate a version")
    prior_version = next(
        value for value in governance.versions() if value.version_id == prior_version_id
    )

    candidate_receipt = governance.create_candidate(
        content=_knowledge_content(
            canonical_sha256=canonical.canonical_sha256,
            process_artifact=canonical.process_artifact,
            evidence_document_plan=canonical.evidence_document_plan,
        ),
        provenance=canonical.provenance,
        timestamp=timestamp,
    )
    candidate_version_id = candidate_receipt.version_id
    quarantine_receipt = governance.quarantine(
        candidate_version_id, timestamp=timestamp
    )
    review_receipt = create_review_receipt(
        reviewer_authority_type=ReviewerAuthorityType.NON_HUMAN_TEST_FIXTURE,
        reviewed_artifact_version=candidate_version_id,
        accepted_corrections=accepted_corrections,
        timestamp=timestamp,
        provenance=canonical.provenance,
    )
    reviewed_receipt = governance.record_review(
        candidate_version_id, review_receipt, timestamp=timestamp
    )
    regression_receipt = create_regression_receipt(
        artifact_version=candidate_version_id,
        test_manifest_sha256=regression_test_manifest_sha256,
        passed=True,
        timestamp=timestamp,
        provenance=canonical.provenance,
    )
    regression_passed_receipt = governance.record_regression(
        candidate_version_id, regression_receipt, timestamp=timestamp
    )
    promotion_receipt = governance.promote(candidate_version_id, timestamp=timestamp)
    retrieval_receipt = governance.retrieve(case_id=later_case_id, timestamp=timestamp)
    rollback_receipt = governance.rollback(timestamp=timestamp)
    restored_version = next(
        value for value in governance.versions() if value.version_id == prior_version_id
    )
    exact_prior_version_restored = (
        governance.active_version_id == prior_version_id
        and restored_version.content_sha256 == prior_version.content_sha256
        and restored_version.content == prior_version.content
        and rollback_receipt.exact_prior_version_restored is True
    )
    replay_payload = {
        "case_id": canonical.case_id,
        "canonical_sha256": canonical.canonical_sha256,
        "validation_receipt_sha256": validation.receipt_sha256,
        "restored_version_id": restored_version.version_id,
        "restored_content_sha256": restored_version.content_sha256,
        "exact_prior_version_restored": exact_prior_version_restored,
        "model_calls": 0,
        "provider_calls": 0,
        "provider_credentials_read": False,
        "cost_usd": 0.0,
    }

    return {
        "privacy_result": privacy_result,
        "case_input": case_input,
        "model_boundary_result": boundary_result,
        "canonical_artifact": canonical,
        "validation_receipt": validation,
        "governance": {
            "initial_receipt": initial_receipt,
            "candidate_receipt": candidate_receipt,
            "quarantine_receipt": quarantine_receipt,
            "review_receipt": review_receipt,
            "reviewed_receipt": reviewed_receipt,
            "regression_receipt": regression_receipt,
            "regression_passed_receipt": regression_passed_receipt,
            "promotion_receipt": promotion_receipt,
            "retrieval_receipt": retrieval_receipt,
            "rollback_receipt": rollback_receipt,
            "versions": governance.versions(),
            "receipts": governance.receipts(),
            "prior_version": prior_version,
            "restored_version": restored_version,
            "exact_prior_version_restored": exact_prior_version_restored,
        },
        "regression_replay": {
            **replay_payload,
            "receipt_sha256": digest_value(replay_payload),
        },
    }
