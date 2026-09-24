"""Typed, byte-bound text projection presented to text-only model arms."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, model_validator

from manifests.digests import digest_json

from .autonomous import Language
from .closed_vocabulary import ClosedVocabularyOntology
from .schema import SourceLocator, StrictModel

FORBIDDEN_EVALUATOR_FIELDS = frozenset(
    {
        "acceptance_contract",
        "accepted_terminal_outcomes",
        "active_when",
        "actual_path",
        "branch_decisions",
        "branch_predicates",
        "evaluator_contract_path",
        "evaluator_sha256",
        "evidence_contracts",
        "expected_claim_category",
        "expected_current_process_state",
        "expected_document_states",
        "expected_next_action",
        "expected_tenant_law_subcategory",
        "ground_truth_kind",
        "hidden_ground_truth",
        "inactive_concept_ids",
        "path_probes",
        "reference_answer",
        "required_concept_ids",
        "scenario",
        "supervision",
    }
)


class ModelVisibleProjection(StrictModel):
    projection_version: Literal["casepath.text-model-projection/1.0.0"]
    extractor_identity: Literal["python-3.13-email+pypdf-6.10.0+jpeg-opaque/1.0.0"]
    case_id: str = Field(min_length=1)
    language: Language
    observable_claim: dict[str, Any]
    closed_vocabulary_ontology: ClosedVocabularyOntology
    source_packet_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    representation_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_hash_and_boundary(self) -> ModelVisibleProjection:
        serialized = self.model_dump(mode="json", exclude={"representation_sha256"})
        if self.representation_sha256 != digest_json(serialized):
            raise ValueError("text-model projection has a stale representation hash")
        forbidden = {*FORBIDDEN_EVALUATOR_FIELDS, "content_base64"}

        def keys(value: Any) -> set[str]:
            if isinstance(value, dict):
                return set(value).union(*(keys(item) for item in value.values()))
            if isinstance(value, list | tuple):
                return set().union(*(keys(item) for item in value), set())
            return set()

        leaked = keys(serialized).intersection(forbidden)
        if leaked:
            raise ValueError(f"text-model projection contains forbidden fields: {sorted(leaked)}")
        return self


class ModelVisibleSourceRegistryEntryV3(StrictModel):
    source_kind: Literal[
        "case_invariant_rule",
        "swiss_authority_passage",
        "observable_message_span",
        "observable_attachment_inventory",
    ]
    display_value: Any
    locator: SourceLocator
    line_number: int | None = Field(default=None, ge=1)
    authority_id: str | None = None
    parent_artifact_id: str | None = None
    parent_artifact_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    representation_identity: str | None = None
    support_scope: Literal["normative", "case_specific", "availability"]


class ModelVisibleSourceRegistryV3(StrictModel):
    contract: Literal["casepath.model-visible-source-registry/3.1.0"]
    case_id: str = Field(min_length=1)
    scope: Literal[
        "all_rules_and_authorities_plus_proposition_sized_message_spans_and_attachment_inventory"
    ]
    entries: tuple[ModelVisibleSourceRegistryEntryV3, ...] = Field(min_length=1)
    contains_case_activation_values: Literal[False]
    contains_selected_paths: Literal[False]
    registry_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_registry(self) -> ModelVisibleSourceRegistryV3:
        if self.registry_sha256 != digest_json(
            self.model_dump(mode="json", exclude={"registry_sha256"})
        ):
            raise ValueError("model-visible source registry hash is stale")
        locator_ids = [digest_json(item.locator.model_dump(mode="json")) for item in self.entries]
        if len(locator_ids) != len(set(locator_ids)):
            raise ValueError("model-visible source registry contains duplicate locators")
        return self


class ModelVisibleProjectionV3(StrictModel):
    projection_version: Literal["casepath.text-model-projection/3.0.0"]
    extractor_identity: Literal["python-3.13-email+pypdf-6.10.0+jpeg-opaque/1.0.0"]
    case_id: str = Field(min_length=1)
    language: Language
    observable_claim: dict[str, Any]
    closed_vocabulary_ontology: ClosedVocabularyOntology
    source_registry: ModelVisibleSourceRegistryV3
    source_packet_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    representation_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_hash_and_boundary(self) -> ModelVisibleProjectionV3:
        serialized = self.model_dump(mode="json", exclude={"representation_sha256"})
        if self.case_id != self.source_registry.case_id:
            raise ValueError("model projection and source registry case IDs differ")
        if self.representation_sha256 != digest_json(serialized):
            raise ValueError("v3 text-model projection has a stale representation hash")
        forbidden = {*FORBIDDEN_EVALUATOR_FIELDS, "content_base64"}

        def keys(value: Any) -> set[str]:
            if isinstance(value, dict):
                return set(value).union(*(keys(item) for item in value.values()))
            if isinstance(value, list | tuple):
                return set().union(*(keys(item) for item in value), set())
            return set()

        leaked = keys(serialized).intersection(forbidden)
        if leaked:
            raise ValueError(
                f"v3 text-model projection contains forbidden fields: {sorted(leaked)}"
            )
        return self
