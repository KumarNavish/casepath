"""Provider-neutral, deterministic CasePath system-foundation contracts.

This package contains no provider SDK imports and performs no model inference. Its
deterministic and offline adapters are architectural test surfaces, not model evidence.
"""

from .case_adapter import (
    assemble_canonical_artifact,
    benchmark_to_canonical,
    benchmark_packet_to_privacy_intake,
    canonical_input_from_privacy,
    canonical_to_benchmark,
    canonical_to_product,
    product_to_canonical,
    reference_candidate_to_model_artifact,
)
from .contracts import (
    CanonicalCaseArtifact,
    CanonicalCaseInput,
    IntakeAttachment,
    KnowledgeState,
    PrivacyIntake,
    PrivacyState,
    ReviewerAuthorityType,
    SeededIdentifier,
    SourceLocator,
)
from .governance import (
    KnowledgeGovernance,
    KnowledgeGovernanceError,
    create_regression_receipt,
    create_review_receipt,
)
from .lifecycle import execute_foundation_lifecycle
from .model_boundary import (
    DeterministicReferenceAdapter,
    FailingTestAdapter,
    ModelBoundaryError,
    OfflineFakeAdapter,
    execute_model_boundary,
)
from .privacy import privacy_gate
from .validation import validate_canonical_artifact

__all__ = [
    "CanonicalCaseArtifact",
    "CanonicalCaseInput",
    "DeterministicReferenceAdapter",
    "FailingTestAdapter",
    "IntakeAttachment",
    "KnowledgeGovernance",
    "KnowledgeGovernanceError",
    "KnowledgeState",
    "ModelBoundaryError",
    "OfflineFakeAdapter",
    "PrivacyIntake",
    "PrivacyState",
    "ReviewerAuthorityType",
    "SeededIdentifier",
    "SourceLocator",
    "assemble_canonical_artifact",
    "benchmark_packet_to_privacy_intake",
    "benchmark_to_canonical",
    "canonical_input_from_privacy",
    "canonical_to_benchmark",
    "canonical_to_product",
    "create_regression_receipt",
    "create_review_receipt",
    "execute_foundation_lifecycle",
    "execute_model_boundary",
    "privacy_gate",
    "product_to_canonical",
    "reference_candidate_to_model_artifact",
    "validate_canonical_artifact",
]
