from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import pytest

from casepath_api.foundation import (
    DeterministicReferenceAdapter,
    FailingTestAdapter,
    KnowledgeGovernance,
    KnowledgeGovernanceError,
    ModelBoundaryError,
    OfflineFakeAdapter,
    PrivacyIntake,
    PrivacyState,
    ReviewerAuthorityType,
    SeededIdentifier,
    SourceLocator,
    assemble_canonical_artifact,
    benchmark_to_canonical,
    canonical_input_from_privacy,
    canonical_to_benchmark,
    canonical_to_product,
    create_regression_receipt,
    create_review_receipt,
    execute_foundation_lifecycle,
    execute_model_boundary,
    privacy_gate,
    product_to_canonical,
    validate_canonical_artifact,
)
from casepath_api.foundation.common import digest_value
from casepath_api.foundation.contracts import IntakeAttachment, ModelArtifact


FIXED_TIME = "2026-08-24T18:48:45+02:00"
SOURCE_HASH = "a" * 64


def locator(*, exact_text: str = "The source requires proof.") -> SourceLocator:
    return SourceLocator(
        artifact_id="source.rules",
        artifact_sha256=SOURCE_HASH,
        locator_kind="text_quote",
        page=1,
        exact_text=exact_text,
    )


def intake(
    *,
    message: str = "A synthetic fixture reports damage.",
    identifiers: tuple[SeededIdentifier, ...] = (),
    declared_safe: bool = True,
    source: SourceLocator | None = None,
) -> PrivacyIntake:
    source_locator = source or locator()
    return PrivacyIntake(
        case_id="public.fixture.001",
        language="en",
        claim_message=message,
        attachments=(
            IntakeAttachment(
                artifact_id="claim.message",
                filename="claim.txt",
                media_type="text/plain",
                source_sha256="b" * 64,
                text=message,
                locators=(source_locator,),
            ),
        ),
        source_locators=(source_locator,),
        seeded_identifiers=identifiers,
        declared_synthetic_or_anonymized=declared_safe,
    )


def model_artifact() -> ModelArtifact:
    provenance = locator().model_dump(mode="json")
    process = {
        "artifact_version": "casepath.candidate-artifact/0.1.0",
        "concepts": [
            {
                "concept_id": "decision.coverage",
                "kind": "decision",
                "label": "Coverage decision",
                "provenance": [provenance],
            },
            {
                "concept_id": "fact.loss",
                "kind": "fact",
                "label": "Loss fact",
                "provenance": [provenance],
            },
            {
                "concept_id": "evidence.loss",
                "kind": "evidence_capability",
                "label": "Loss evidence",
                "provenance": [provenance],
            },
            {
                "concept_id": "outcome.covered",
                "kind": "outcome",
                "label": "Covered",
                "provenance": [provenance],
            },
        ],
        "relations": [
            {
                "relation_id": "relation.requires",
                "relation_type": "requires_fact",
                "source_id": "decision.coverage",
                "target_id": "fact.loss",
            },
            {
                "relation_id": "relation.supported",
                "relation_type": "supported_by",
                "source_id": "fact.loss",
                "target_id": "evidence.loss",
            },
            {
                "relation_id": "relation.satisfied",
                "relation_type": "satisfied_by",
                "source_id": "evidence.loss",
                "target_id": "candidate.document.loss",
            },
            {
                "relation_id": "relation.outcome",
                "relation_type": "leads_to",
                "source_id": "decision.coverage",
                "target_id": "outcome.covered",
            },
        ],
        "branch_predicates": [
            {
                "predicate_id": "predicate.coverage",
                "expression": "coverage_applies == true",
                "provenance": [provenance],
            }
        ],
        "terminal_outcome_ids": ["outcome.covered"],
        "abstained_concept_ids": [],
    }
    documents = (
        {
            "item_id": "candidate.document.loss",
            "document_id": "document.loss",
            "label": "Loss proof",
            "state": "missing",
            "request_mode": "now",
            "provenance": [provenance],
        },
    )
    payload = {
        "contract": "casepath.provider-neutral-model-artifact/1.0.0",
        "case_id": "public.fixture.001",
        "process_artifact": process,
        "evidence_document_plan": documents,
        "provenance": [provenance],
    }
    return ModelArtifact.model_validate(
        {**payload, "artifact_sha256": digest_value(payload)}
    )


def canonical_artifact() -> Any:
    admitted = privacy_gate(intake())
    case_input = canonical_input_from_privacy(intake(), admitted)
    boundary = execute_model_boundary(
        DeterministicReferenceAdapter({case_input.case_id: model_artifact()}),
        case_input,
    )
    return assemble_canonical_artifact(
        case_input,
        boundary.artifact,
        model_boundary_receipt_sha256=boundary.receipt.receipt_sha256,
    )


def test_privacy_gate_replaces_seeded_identifiers_and_preserves_lineage() -> None:
    email = SeededIdentifier(
        identifier_id="person.email",
        kind="email_address",
        value="ada@example.ch",
        replacement_token="[EMAIL_1]",
    )
    address = SeededIdentifier(
        identifier_id="person.address",
        kind="street_address",
        value="Musterstrasse 7, 8000 Zurich",
        replacement_token="[ADDRESS_1]",
    )
    source = locator(
        exact_text="Contact ada@example.ch about Musterstrasse 7, 8000 Zurich"
    )
    original = intake(
        message="ada@example.ch lives at Musterstrasse 7, 8000 Zurich",
        identifiers=(email, address),
        declared_safe=False,
        source=source,
    )
    result = privacy_gate(original)

    assert result.state == PrivacyState.SAFE_TO_PROCESS
    assert result.sanitized_message == "[EMAIL_1] lives at [ADDRESS_1]"
    assert (
        result.source_locators[0].artifact_sha256
        == original.source_locators[0].artifact_sha256
    )
    assert (
        result.source_locators[0].artifact_id == original.source_locators[0].artifact_id
    )
    assert result.source_locators[0].exact_text == "Contact [EMAIL_1] about [ADDRESS_1]"
    assert sum(value.replacement_count for value in result.receipt.replacements) >= 4
    assert result.receipt.fail_closed is False


@pytest.mark.parametrize(
    ("message", "expected_class"),
    [
        ("Reply to unresolved@example.ch.", "email_address"),
        ("Policy LP-2026-123456 remains visible.", "policy_reference"),
        ("Transfer to CH9300762011623852957.", "iban"),
        ("Call +41 79 123 45 67.", "phone_number"),
        ("Send mail to Musterstrasse 7, 8000 Zurich.", "street_address"),
    ],
)
def test_privacy_gate_fails_closed_on_unresolved_high_risk_input(
    message: str, expected_class: str
) -> None:
    result = privacy_gate(intake(message=message, declared_safe=False))

    assert result.state == PrivacyState.BLOCKED_FOR_UNRESOLVED_IDENTIFIERS
    assert result.sanitized_message is None
    assert result.sanitized_attachments == ()
    assert result.source_locators == ()
    assert expected_class in result.receipt.unresolved_identifier_classes
    assert result.receipt.fail_closed is True


def test_declared_synthetic_fixture_is_admitted_with_explicit_nonclaim() -> None:
    result = privacy_gate(
        intake(
            message="Synthetic resident at Musterstrasse 7, 8000 Zurich.",
            declared_safe=True,
        )
    )

    assert result.state == PrivacyState.ALREADY_SYNTHETIC_OR_ANONYMIZED
    assert "street_address" in result.receipt.unresolved_identifier_classes
    assert result.receipt.fail_closed is False
    assert result.receipt.fixture_scope_only is True
    assert (
        "does not establish general anonymization safety"
        in result.receipt.safety_nonclaim
    )


def test_provider_neutral_adapters_conform_without_provider_imports() -> None:
    admitted = privacy_gate(intake())
    case_input = canonical_input_from_privacy(intake(), admitted)
    artifact = model_artifact()

    for adapter in (
        DeterministicReferenceAdapter({case_input.case_id: artifact}),
        OfflineFakeAdapter({case_input.case_id: artifact}),
    ):
        result = execute_model_boundary(adapter, case_input)
        assert result.receipt.model_calls == 0
        assert result.receipt.provider_calls == 0
        assert result.receipt.provider_credentials_read is False
        assert result.receipt.cost_usd == 0.0

    with pytest.raises(ModelBoundaryError, match="not admissible"):
        execute_model_boundary(FailingTestAdapter(), case_input)

    foundation_dir = Path(__file__).parents[1] / "casepath_api" / "foundation"
    forbidden_roots = {
        "anthropic",
        "langchain",
        "langchain_openrouter",
        "openai",
        "openrouter",
    }
    imports: set[str] = set()
    for path in foundation_dir.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                imports.add(node.module.split(".")[0])
    assert imports.isdisjoint(forbidden_roots)


def test_canonical_product_and_benchmark_round_trips_are_lossless() -> None:
    canonical = canonical_artifact()

    product_roundtrip = product_to_canonical(canonical_to_product(canonical))
    benchmark_roundtrip = benchmark_to_canonical(canonical_to_benchmark(canonical))

    assert product_roundtrip == canonical
    assert benchmark_roundtrip == canonical
    assert product_roundtrip.canonical_sha256 == canonical.canonical_sha256
    assert benchmark_roundtrip.canonical_sha256 == canonical.canonical_sha256


def _advance_to_quarantined(
    governance: KnowledgeGovernance,
) -> tuple[str, tuple[SourceLocator, ...]]:
    provenance = (locator(),)
    governance.install_initial(
        content={"baseline": True}, provenance=provenance, timestamp=FIXED_TIME
    )
    candidate = governance.create_candidate(
        content={"candidate": True}, provenance=provenance, timestamp=FIXED_TIME
    )
    governance.quarantine(candidate.version_id, timestamp=FIXED_TIME)
    return candidate.version_id, provenance


def test_governance_rejects_bypass_and_nonhuman_receipt_without_fixture_mode() -> None:
    governance = KnowledgeGovernance()
    version_id, provenance = _advance_to_quarantined(governance)

    with pytest.raises(KnowledgeGovernanceError, match="regression_passed"):
        governance.promote(version_id, timestamp=FIXED_TIME)

    fixture_review = create_review_receipt(
        reviewer_authority_type=ReviewerAuthorityType.NON_HUMAN_TEST_FIXTURE,
        reviewed_artifact_version=version_id,
        accepted_corrections=(),
        timestamp=FIXED_TIME,
        provenance=provenance,
    )
    with pytest.raises(KnowledgeGovernanceError, match="explicit fixture mode"):
        governance.record_review(version_id, fixture_review, timestamp=FIXED_TIME)


def test_governance_requires_review_regression_and_exact_rollback() -> None:
    governance = KnowledgeGovernance(allow_non_human_test_fixture=True)
    version_id, provenance = _advance_to_quarantined(governance)
    prior_id = governance.active_version_id
    prior = next(
        value for value in governance.versions() if value.version_id == prior_id
    )

    review = create_review_receipt(
        reviewer_authority_type=ReviewerAuthorityType.NON_HUMAN_TEST_FIXTURE,
        reviewed_artifact_version=version_id,
        accepted_corrections=({"fixture": "no semantic change"},),
        timestamp=FIXED_TIME,
        provenance=provenance,
    )
    governance.record_review(version_id, review, timestamp=FIXED_TIME)
    with pytest.raises(KnowledgeGovernanceError, match="regression_passed"):
        governance.promote(version_id, timestamp=FIXED_TIME)

    regression = create_regression_receipt(
        artifact_version=version_id,
        test_manifest_sha256="c" * 64,
        passed=True,
        timestamp=FIXED_TIME,
        provenance=provenance,
    )
    governance.record_regression(version_id, regression, timestamp=FIXED_TIME)
    governance.promote(version_id, timestamp=FIXED_TIME)
    retrieval = governance.retrieve(
        case_id="later.public.fixture", timestamp=FIXED_TIME
    )
    rollback = governance.rollback(timestamp=FIXED_TIME)
    restored = next(
        value for value in governance.versions() if value.version_id == prior_id
    )

    assert retrieval.active_version_id == version_id
    assert rollback.exact_prior_version_restored is True
    assert governance.active_version_id == prior_id
    assert restored.content == prior.content
    assert restored.content_sha256 == prior.content_sha256
    assert restored.provenance == prior.provenance


def test_validation_and_complete_deterministic_lifecycle_are_replayable() -> None:
    artifact = model_artifact()
    canonical = canonical_artifact()
    validation = validate_canonical_artifact(canonical)
    assert validation.passed is True

    kwargs = {
        "intake": intake(),
        "adapter": DeterministicReferenceAdapter({artifact.case_id: artifact}),
        "initial_knowledge_content": {"baseline": "public deterministic fixture"},
        "initial_knowledge_provenance": (locator(),),
        "accepted_corrections": ({"fixture": "accepted without semantic edit"},),
        "regression_test_manifest_sha256": "d" * 64,
        "later_case_id": "later.public.fixture",
        "timestamp": FIXED_TIME,
    }
    first = execute_foundation_lifecycle(**kwargs)
    second = execute_foundation_lifecycle(**kwargs)

    assert first["governance"]["exact_prior_version_restored"] is True
    assert first["regression_replay"]["model_calls"] == 0
    assert first["regression_replay"]["provider_calls"] == 0
    assert first["regression_replay"]["cost_usd"] == 0.0
    assert digest_value(_jsonable(first)) == digest_value(_jsonable(second))


def _jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    return value
