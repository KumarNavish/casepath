"""Gold-blind verifier for candidate-internal consistency.

The module intentionally cannot import AcceptanceContract. It may remove or
abstain from unsupported candidate assertions; it may never add facts,
relations, evidence capabilities, or documents.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from contracts.expressions import ExpressionError, evaluate_expression, referenced_names
from contracts.schema import (
    CandidateArtifact,
    ConceptKind,
    PublicScenarioAssignment,
    RelationType,
    RequestMode,
)
from manifests.digests import digest_json


@dataclass(frozen=True)
class VerificationReceipt:
    verifier_version: str
    source_condition_id: Literal["B7", "PF_TYPED_V3"]
    input_candidate_sha256: str
    output_candidate_sha256: str
    scenario_sha256: str
    additional_model_calls: Literal[0]
    removed_request_item_ids: tuple[str, ...]
    violations: tuple[str, ...]
    input_concept_count: int
    output_concept_count: int
    input_relation_count: int
    output_relation_count: int
    input_document_count: int
    output_document_count: int


class ContractFreeVerifier:
    """Suppress requests without a fully active typed chain under public state."""

    version = "casepath.contract-free-verifier/0.4.0"

    @staticmethod
    def _active(expression: str, scenario: PublicScenarioAssignment) -> bool:
        """Evaluate a public predicate; missing or invalid inputs are inactive."""

        try:
            values: dict[str, Any] = {str(key): value for key, value in scenario.items()}
            names = referenced_names(expression)
            if not names.issubset(values) or any(type(values[name]) is not bool for name in names):
                return False
            return evaluate_expression(expression, values)
        except (ExpressionError, TypeError, ValueError):
            return False

    def verify(
        self,
        candidate: CandidateArtifact,
        scenario: PublicScenarioAssignment,
        *,
        source_condition_id: Literal["B7", "PF_TYPED_V3"] = "B7",
    ) -> tuple[CandidateArtifact, VerificationReceipt]:
        concepts = {concept.concept_id: concept for concept in candidate.concepts}
        decisions = {
            concept_id
            for concept_id, concept in concepts.items()
            if concept.kind is ConceptKind.DECISION and self._active(concept.active_when, scenario)
        }
        facts = {
            concept_id
            for concept_id, concept in concepts.items()
            if concept.kind is ConceptKind.FACT and self._active(concept.active_when, scenario)
        }
        capabilities = {
            concept_id
            for concept_id, concept in concepts.items()
            if concept.kind is ConceptKind.EVIDENCE_CAPABILITY
            and self._active(concept.active_when, scenario)
        }
        edges = {
            (relation.relation_type, relation.source_id, relation.target_id)
            for relation in candidate.relations
            if self._active(relation.active_when, scenario)
        }
        active_documents = {
            document.item_id
            for document in candidate.documents
            if self._active(document.active_when, scenario)
        }
        justified_items: set[str] = set()
        for decision in decisions:
            linked_facts = {
                fact for fact in facts if (RelationType.REQUIRES_FACT, decision, fact) in edges
            }
            for fact in linked_facts:
                linked_capabilities = {
                    capability
                    for capability in capabilities
                    if (RelationType.SUPPORTED_BY, fact, capability) in edges
                }
                for capability in linked_capabilities:
                    justified_items.update(
                        target
                        for relation_type, source, target in edges
                        if relation_type is RelationType.SATISFIED_BY
                        and source == capability
                        and target in active_documents
                    )

        removed: list[str] = []
        violations: list[str] = []
        documents = []
        for document in candidate.documents:
            if document.request_mode is not RequestMode.NONE and (
                document.item_id not in active_documents or document.item_id not in justified_items
            ):
                removed.append(document.item_id)
                violations.append(
                    f"{document.item_id} has no entirely active candidate-internal "
                    "decision→fact→capability→document chain under the public scenario"
                )
                document = document.model_copy(update={"request_mode": RequestMode.NONE})
            documents.append(document)
        verified = candidate.model_copy(update={"documents": tuple(documents)})
        receipt = VerificationReceipt(
            verifier_version=self.version,
            source_condition_id=source_condition_id,
            input_candidate_sha256=digest_json(candidate.model_dump(mode="json")),
            output_candidate_sha256=digest_json(verified.model_dump(mode="json")),
            scenario_sha256=digest_json(scenario),
            additional_model_calls=0,
            removed_request_item_ids=tuple(removed),
            violations=tuple(violations),
            input_concept_count=len(candidate.concepts),
            output_concept_count=len(verified.concepts),
            input_relation_count=len(candidate.relations),
            output_relation_count=len(verified.relations),
            input_document_count=len(candidate.documents),
            output_document_count=len(verified.documents),
        )
        if (
            receipt.input_concept_count != receipt.output_concept_count
            or receipt.input_relation_count != receipt.output_relation_count
            or receipt.input_document_count != receipt.output_document_count
        ):
            raise RuntimeError("verifier violated its non-addition/non-deletion contract")
        return verified, receipt
