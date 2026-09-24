"""Typed contracts for the paired CasePath document-state stress track."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from contracts.schema import DocumentState, RequestMode, StrictModel
from manifests.digests import digest_json

Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
StressVariantV3 = Literal[
    "add_sufficient_artifact",
    "deactivate_requirement",
    "defer_conditional_requirement",
    "resolve_all_active_requirements",
]


class StateStressObservableUpdateV3(StrictModel):
    update_id: str = Field(pattern=r"^update\.[a-z0-9._-]+$")
    update_kind: Literal[
        "sufficient_artifact",
        "branch_fact_false",
        "branch_fact_unresolved",
        "all_active_facts_resolved",
    ]
    target_ids: tuple[str, ...] = Field(min_length=1)
    statement: str = Field(min_length=1, max_length=4000)
    update_sha256: Sha256

    @model_validator(mode="after")
    def validate_update(self) -> StateStressObservableUpdateV3:
        if self.update_sha256 != digest_json(
            self.model_dump(mode="json", exclude={"update_sha256"})
        ):
            raise ValueError("state-stress observable update hash is stale")
        return self


class StateStressPublicCaseV3(StrictModel):
    contract: Literal["casepath.state-stress-public-case/3.0.0"]
    stress_case_id: str = Field(pattern=r"^stress\.[0-9a-f]{24}$")
    base_case_id: str = Field(min_length=1)
    domain: str = Field(min_length=1)
    family_id: str = Field(min_length=1)
    split: Literal["public_dev", "hidden_test"]
    variant: StressVariantV3
    base_observable_claim_path: str = Field(min_length=1)
    base_source_registry_path: str = Field(min_length=1)
    observable_updates: tuple[StateStressObservableUpdateV3, ...] = Field(min_length=1)
    public_input_sha256: Sha256

    @model_validator(mode="after")
    def validate_case(self) -> StateStressPublicCaseV3:
        if self.public_input_sha256 != digest_json(
            self.model_dump(mode="json", exclude={"public_input_sha256"})
        ):
            raise ValueError("state-stress public input hash is stale")
        return self


class StateStressDocumentDecisionV3(StrictModel):
    document_id: str = Field(min_length=1)
    state: DocumentState
    request_mode: RequestMode
    support_update_ids: tuple[str, ...] = ()


class StateStressExpectedV3(StrictModel):
    contract: Literal["casepath.state-stress-expected/3.0.0"]
    stress_case_id: str = Field(pattern=r"^stress\.[0-9a-f]{24}$")
    base_case_id: str = Field(min_length=1)
    variant: StressVariantV3
    document_decisions: tuple[StateStressDocumentDecisionV3, ...] = Field(min_length=1)
    active_concept_ids: tuple[str, ...]
    active_relation_ids: tuple[str, ...]
    terminal_outcome_ids: tuple[str, ...] = Field(min_length=1)
    unaffected_concept_ids: tuple[str, ...]
    unaffected_relation_ids: tuple[str, ...]
    expected_sha256: Sha256

    @model_validator(mode="after")
    def validate_expected(self) -> StateStressExpectedV3:
        if len({item.document_id for item in self.document_decisions}) != len(
            self.document_decisions
        ):
            raise ValueError("state-stress expected document IDs repeat")
        update_ids = {
            update_id
            for decision in self.document_decisions
            for update_id in decision.support_update_ids
        }
        if any(not value.startswith("update.") for value in update_ids):
            raise ValueError("state-stress support IDs are not observable updates")
        if self.expected_sha256 != digest_json(
            self.model_dump(mode="json", exclude={"expected_sha256"})
        ):
            raise ValueError("state-stress expected contract hash is stale")
        return self


class StateStressPredictionV3(StrictModel):
    contract: Literal["casepath.state-stress-prediction/3.0.0"]
    stress_case_id: str = Field(pattern=r"^stress\.[0-9a-f]{24}$")
    document_decisions: tuple[StateStressDocumentDecisionV3, ...]
    active_concept_ids: tuple[str, ...]
    active_relation_ids: tuple[str, ...]
    terminal_outcome_ids: tuple[str, ...]


class StateStressScoreV3(StrictModel):
    contract: Literal["casepath.state-stress-score/3.0.0"]
    stress_case_id: str
    state_transition_accuracy: float = Field(ge=0.0, le=1.0)
    request_mode_accuracy: float = Field(ge=0.0, le=1.0)
    immediate_request_set_exact: float = Field(ge=0.0, le=1.0)
    conditional_request_set_exact: float = Field(ge=0.0, le=1.0)
    empty_request_stopping_accuracy: float = Field(ge=0.0, le=1.0)
    active_graph_accuracy: float = Field(ge=0.0, le=1.0)
    unaffected_graph_invariance: float = Field(ge=0.0, le=1.0)
    observable_update_support_accuracy: float = Field(ge=0.0, le=1.0)
    unnecessary_request_rate: float = Field(ge=0.0, le=1.0)
    score_sha256: Sha256

    @model_validator(mode="after")
    def validate_score(self) -> StateStressScoreV3:
        if self.score_sha256 != digest_json(self.model_dump(mode="json", exclude={"score_sha256"})):
            raise ValueError("state-stress score hash is stale")
        return self


class StateStressManifestRowV3(StrictModel):
    stress_case_id: str
    base_case_id: str
    domain: str
    family_id: str
    split: Literal["public_dev", "hidden_test"]
    variant: StressVariantV3
    public_case_path: str
    public_case_sha256: Sha256
    public_gold_path: str | None
    hidden_expected_commitment_sha256: Sha256 | None
    row_sha256: Sha256

    @model_validator(mode="after")
    def validate_row(self) -> StateStressManifestRowV3:
        if (self.split == "public_dev") != (self.public_gold_path is not None):
            raise ValueError("state-stress dev/test gold boundary differs")
        if (self.split == "hidden_test") != (self.hidden_expected_commitment_sha256 is not None):
            raise ValueError("state-stress hidden commitment boundary differs")
        if self.row_sha256 != digest_json(self.model_dump(mode="json", exclude={"row_sha256"})):
            raise ValueError("state-stress manifest row hash is stale")
        return self


class StateStressManifestV3(StrictModel):
    contract: Literal["casepath.state-stress-manifest/3.0.0"]
    benchmark_id: Literal["casepath-state-stress-v3"]
    construction: Literal[
        "deterministic_paired_generator_state_transitions_no_model_or_expert_calls"
    ]
    base_case_count: Literal[12]
    variant_count: Literal[48]
    public_dev_variant_count: Literal[24]
    hidden_test_variant_count: Literal[24]
    variants: tuple[StateStressManifestRowV3, ...] = Field(min_length=48, max_length=48)
    endpoint_ids: tuple[str, ...]
    runtime_model_calls: Literal[0]
    experts_required: Literal[False]
    manifest_sha256: Sha256

    @model_validator(mode="after")
    def validate_manifest(self) -> StateStressManifestV3:
        if len({item.stress_case_id for item in self.variants}) != 48:
            raise ValueError("state-stress case IDs repeat")
        if len({item.base_case_id for item in self.variants}) != 12:
            raise ValueError("state-stress base roster differs")
        if {item.variant for item in self.variants} != {
            "add_sufficient_artifact",
            "deactivate_requirement",
            "defer_conditional_requirement",
            "resolve_all_active_requirements",
        }:
            raise ValueError("state-stress transition types are incomplete")
        if self.manifest_sha256 != digest_json(
            self.model_dump(mode="json", exclude={"manifest_sha256"})
        ):
            raise ValueError("state-stress manifest hash is stale")
        return self
