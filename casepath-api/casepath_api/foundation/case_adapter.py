from __future__ import annotations

from typing import Any

from .common import digest_value
from .contracts import (
    CanonicalCaseArtifact,
    CanonicalCaseInput,
    IntakeAttachment,
    ModelArtifact,
    PrivacyIntake,
    PrivacyResult,
    PrivacyState,
    SourceLocator,
)


def _locator(value: dict[str, Any]) -> SourceLocator:
    allowed = set(SourceLocator.model_fields)
    return SourceLocator.model_validate(
        {key: item for key, item in value.items() if key in allowed}
    )


def _dedupe_locators(values: list[SourceLocator]) -> tuple[SourceLocator, ...]:
    by_hash = {digest_value(value.model_dump(mode="json")): value for value in values}
    return tuple(by_hash[key] for key in sorted(by_hash))


def _representation_text(value: dict[str, Any]) -> str:
    representation = value.get("representation")
    if not isinstance(representation, dict):
        return ""
    text = representation.get("text")
    if isinstance(text, str):
        return text
    pages = representation.get("pages")
    if isinstance(pages, list):
        texts = [
            page.get("text", "")
            for page in pages
            if isinstance(page, dict) and isinstance(page.get("text"), str)
        ]
        return "\n\n".join(texts)
    return ""


def benchmark_packet_to_privacy_intake(packet: dict[str, Any]) -> PrivacyIntake:
    observable = packet["observable_claim"]
    submission = observable["submission"]
    message_source = observable["message_source"]
    attachments = [message_source, *observable.get("attachments", [])]
    intake_attachments = tuple(
        IntakeAttachment(
            artifact_id=value["artifact_id"],
            filename=value.get("file_name", value["artifact_id"]),
            media_type=value["media_type"],
            source_sha256=value["sha256"],
            text=_representation_text(value),
            locators=(),
        )
        for value in attachments
    )
    source_locators = tuple(
        _locator(entry["locator"]) for entry in packet["source_registry"]["entries"]
    )
    return PrivacyIntake(
        case_id=packet["case_id"],
        language=packet["language"],
        claim_message=_representation_text(message_source),
        attachments=intake_attachments,
        source_locators=source_locators,
        seeded_identifiers=(),
        declared_synthetic_or_anonymized=(
            submission.get("claim_id") == packet["case_id"]
            and packet.get("projection_version")
            == "casepath.text-model-projection/3.0.0"
        ),
    )


def canonical_input_from_privacy(
    intake: PrivacyIntake, result: PrivacyResult
) -> CanonicalCaseInput:
    if result.state == PrivacyState.BLOCKED_FOR_UNRESOLVED_IDENTIFIERS:
        raise ValueError("privacy gate blocked the case")
    if result.sanitized_message is None:
        raise ValueError("admitted privacy result must contain a sanitized message")
    return CanonicalCaseInput(
        case_id=intake.case_id,
        language=intake.language,
        claim_message=result.sanitized_message,
        attachments=result.sanitized_attachments,
        source_locators=result.source_locators,
        privacy_receipt_sha256=result.receipt.receipt_sha256,
    )


def reference_candidate_to_model_artifact(
    case_id: str, candidate: dict[str, Any]
) -> ModelArtifact:
    provenance: list[SourceLocator] = []
    for collection in (
        candidate.get("concepts", []),
        candidate.get("branch_predicates", []),
        candidate.get("documents", []),
    ):
        for value in collection:
            provenance.extend(
                _locator(locator) for locator in value.get("provenance", [])
            )
    process_artifact = {
        "artifact_version": candidate["artifact_version"],
        "concepts": candidate["concepts"],
        "relations": candidate["relations"],
        "branch_predicates": candidate["branch_predicates"],
        "terminal_outcome_ids": candidate["terminal_outcome_ids"],
        "abstained_concept_ids": candidate["abstained_concept_ids"],
    }
    evidence_document_plan = tuple(candidate["documents"])
    artifact_payload = {
        "contract": "casepath.provider-neutral-model-artifact/1.0.0",
        "case_id": case_id,
        "process_artifact": process_artifact,
        "evidence_document_plan": evidence_document_plan,
        "provenance": [
            value.model_dump(mode="json") for value in _dedupe_locators(provenance)
        ],
    }
    return ModelArtifact.model_validate(
        {**artifact_payload, "artifact_sha256": digest_value(artifact_payload)}
    )


def assemble_canonical_artifact(
    case_input: CanonicalCaseInput,
    model_artifact: ModelArtifact,
    *,
    model_boundary_receipt_sha256: str,
    review_state: str = "unreviewed",
    knowledge_version: str = "none",
) -> CanonicalCaseArtifact:
    if case_input.case_id != model_artifact.case_id:
        raise ValueError("model artifact case identity mismatch")
    payload = {
        "contract": "casepath.canonical-case-artifact/1.0.0",
        "case_id": case_input.case_id,
        "language": case_input.language,
        "claim_message": case_input.claim_message,
        "attachments": [
            value.model_dump(mode="json") for value in case_input.attachments
        ],
        "source_locators": [
            value.model_dump(mode="json") for value in case_input.source_locators
        ],
        "process_artifact": model_artifact.process_artifact,
        "evidence_document_plan": list(model_artifact.evidence_document_plan),
        "provenance": [
            value.model_dump(mode="json") for value in model_artifact.provenance
        ],
        "review_state": review_state,
        "knowledge_version": knowledge_version,
        "privacy_receipt_sha256": case_input.privacy_receipt_sha256,
        "model_boundary_receipt_sha256": model_boundary_receipt_sha256,
    }
    return CanonicalCaseArtifact.model_validate(
        {**payload, "canonical_sha256": digest_value(payload)}
    )


def canonical_to_product(value: CanonicalCaseArtifact) -> dict[str, Any]:
    """Project canonical semantics into the product boundary without an opaque payload."""

    return {
        "contract": "casepath.product-foundation-projection/1.0.0",
        "claim": {
            "case_id": value.case_id,
            "language": value.language,
            "message": value.claim_message,
            "attachments": [item.model_dump(mode="json") for item in value.attachments],
        },
        "source_locators": [
            item.model_dump(mode="json") for item in value.source_locators
        ],
        "process": value.process_artifact,
        "checklist": list(value.evidence_document_plan),
        "provenance": [item.model_dump(mode="json") for item in value.provenance],
        "review_state": value.review_state,
        "knowledge_version": value.knowledge_version,
        "privacy_receipt_sha256": value.privacy_receipt_sha256,
        "model_boundary_receipt_sha256": value.model_boundary_receipt_sha256,
        "canonical_sha256": value.canonical_sha256,
    }


def product_to_canonical(value: dict[str, Any]) -> CanonicalCaseArtifact:
    if value.get("contract") != "casepath.product-foundation-projection/1.0.0":
        raise ValueError("unsupported product foundation projection")
    claim = value["claim"]
    return CanonicalCaseArtifact(
        case_id=claim["case_id"],
        language=claim["language"],
        claim_message=claim["message"],
        attachments=tuple(
            IntakeAttachment.model_validate(item) for item in claim["attachments"]
        ),
        source_locators=tuple(_locator(item) for item in value["source_locators"]),
        process_artifact=value["process"],
        evidence_document_plan=tuple(value["checklist"]),
        provenance=tuple(_locator(item) for item in value["provenance"]),
        review_state=value["review_state"],
        knowledge_version=value["knowledge_version"],
        privacy_receipt_sha256=value["privacy_receipt_sha256"],
        model_boundary_receipt_sha256=value["model_boundary_receipt_sha256"],
        canonical_sha256=value["canonical_sha256"],
    )


def canonical_to_benchmark(value: CanonicalCaseArtifact) -> dict[str, Any]:
    """Project the same canonical semantics into the benchmark adapter boundary."""

    return {
        "contract": "casepath.benchmark-foundation-projection/1.0.0",
        "case_id": value.case_id,
        "language": value.language,
        "observable_claim": {
            "message": value.claim_message,
            "attachments": [item.model_dump(mode="json") for item in value.attachments],
        },
        "source_registry": [
            item.model_dump(mode="json") for item in value.source_locators
        ],
        "candidate": {
            "process_artifact": value.process_artifact,
            "evidence_document_plan": list(value.evidence_document_plan),
            "provenance": [item.model_dump(mode="json") for item in value.provenance],
        },
        "review_state": value.review_state,
        "knowledge_version": value.knowledge_version,
        "privacy_receipt_sha256": value.privacy_receipt_sha256,
        "model_boundary_receipt_sha256": value.model_boundary_receipt_sha256,
        "canonical_sha256": value.canonical_sha256,
    }


def benchmark_to_canonical(value: dict[str, Any]) -> CanonicalCaseArtifact:
    if value.get("contract") != "casepath.benchmark-foundation-projection/1.0.0":
        raise ValueError("unsupported benchmark foundation projection")
    observable = value["observable_claim"]
    candidate = value["candidate"]
    return CanonicalCaseArtifact(
        case_id=value["case_id"],
        language=value["language"],
        claim_message=observable["message"],
        attachments=tuple(
            IntakeAttachment.model_validate(item) for item in observable["attachments"]
        ),
        source_locators=tuple(_locator(item) for item in value["source_registry"]),
        process_artifact=candidate["process_artifact"],
        evidence_document_plan=tuple(candidate["evidence_document_plan"]),
        provenance=tuple(_locator(item) for item in candidate["provenance"]),
        review_state=value["review_state"],
        knowledge_version=value["knowledge_version"],
        privacy_receipt_sha256=value["privacy_receipt_sha256"],
        model_boundary_receipt_sha256=value["model_boundary_receipt_sha256"],
        canonical_sha256=value["canonical_sha256"],
    )
