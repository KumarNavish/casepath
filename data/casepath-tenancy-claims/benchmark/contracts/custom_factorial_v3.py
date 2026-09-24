"""Fail-closed contracts for the public CasePath-Bench-v3 factorial study."""

from __future__ import annotations

import math
import re
from collections import Counter
from pathlib import PurePosixPath
from typing import Annotated, Literal

from pydantic import Field, model_validator

from manifests.digests import digest_json

from .schema import StrictModel

Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
FactorialConditionIdV3 = Literal[
    "PF_TYPED_V3",
    "PF_PLAIN_V3",
    "DIRECT_TYPED_V3",
    "DIRECT_PLAIN_V3",
]
GenerativeConditionIdV3 = Literal[
    "PF_TYPED_V3",
    "PF_PLAIN_V3",
    "DIRECT_TYPED_V3",
    "DIRECT_PLAIN_V3",
    "EXIDE_V3",
    "DOCUMENT_FIRST_V3",
]
ConditionIdV3 = Literal[
    "PF_TYPED_V3",
    "PF_PLAIN_V3",
    "DIRECT_TYPED_V3",
    "DIRECT_PLAIN_V3",
    "EXIDE_V3",
    "DOCUMENT_FIRST_V3",
    "VERIFY_PF_TYPED_V3",
    "ONTOLOGY_RULE_HEURISTIC_V3",
]
EndpointIdV3 = Literal[
    "behavioral_valid_path_rate",
    "branch_predicate_accuracy",
    "required_node_recall",
    "required_edge_recall",
    "critical_evidence_recall",
    "unnecessary_document_rate",
    "document_state_accuracy",
    "valid_chain_precision",
    "fact_chain_completeness",
    "evidence_obligation_completeness",
    "source_grounding_exactness",
]
DomainV3 = Literal[
    "defect_mold_heating",
    "lease_termination_dispute",
    "rent_increase_dispute",
]


class FactorialCellV3(StrictModel):
    condition_id: FactorialConditionIdV3
    order: Literal["process_first", "direct_neutral"]
    representation: Literal["typed", "plain_text"]
    calls: Literal[2]
    final_contract: Literal["casepath.candidate-artifact/0.1.0"]
    information_requirement_set: Literal["shared_seven_kind_set_v3"]
    token_ceiling_policy: Literal["identical_across_all_generative_conditions"]


class ContrastTermV3(StrictModel):
    condition_id: FactorialConditionIdV3
    coefficient: float


class FactorialContrastV3(StrictModel):
    contrast_id: Literal[
        "ORDER_MAIN",
        "REPRESENTATION_MAIN",
        "ORDER_X_REPRESENTATION",
    ]
    interpretation: str = Field(min_length=1)
    terms: tuple[ContrastTermV3, ...] = Field(min_length=4, max_length=4)

    @model_validator(mode="after")
    def validate_contrast(self) -> FactorialContrastV3:
        observed = {term.condition_id: term.coefficient for term in self.terms}
        expected = {
            "ORDER_MAIN": {
                "PF_TYPED_V3": 0.5,
                "PF_PLAIN_V3": 0.5,
                "DIRECT_TYPED_V3": -0.5,
                "DIRECT_PLAIN_V3": -0.5,
            },
            "REPRESENTATION_MAIN": {
                "PF_TYPED_V3": 0.5,
                "PF_PLAIN_V3": -0.5,
                "DIRECT_TYPED_V3": 0.5,
                "DIRECT_PLAIN_V3": -0.5,
            },
            "ORDER_X_REPRESENTATION": {
                "PF_TYPED_V3": 1.0,
                "PF_PLAIN_V3": -1.0,
                "DIRECT_TYPED_V3": -1.0,
                "DIRECT_PLAIN_V3": 1.0,
            },
        }[self.contrast_id]
        if observed != expected or len(self.terms) != 4:
            raise ValueError(f"{self.contrast_id} coefficients differ from the frozen factorial")
        return self


class FactorialHypothesisV3(StrictModel):
    hypothesis_id: str = Field(min_length=1)
    contrast_id: Literal["ORDER_MAIN", "REPRESENTATION_MAIN", "ORDER_X_REPRESENTATION"]
    endpoint_id: EndpointIdV3
    benefit_direction: Literal["higher", "lower"]
    decision_rule: Literal["superiority", "noninferiority", "two_sided_interaction"]
    margin: float = Field(ge=0.0, le=0.1)


class PairwiseHypothesisV3(StrictModel):
    hypothesis_id: str = Field(min_length=1)
    treatment: ConditionIdV3
    control: ConditionIdV3
    endpoint_id: EndpointIdV3
    benefit_direction: Literal["higher", "lower"]
    decision_rule: Literal["superiority", "noninferiority"]
    margin: float = Field(ge=0.0, le=0.1)


class MultiplicityFamilyV3(StrictModel):
    family_id: Literal[
        "order_headline",
        "factorial_mechanism",
        "verifier_falsification",
        "exide_falsification",
        "document_first_falsification",
    ]
    correction: Literal["holm"]
    familywise_alpha: float = Field(gt=0.0, lt=1.0)
    required_for_benchmark_order_claim: bool
    factorial_hypotheses: tuple[FactorialHypothesisV3, ...] = ()
    pairwise_hypotheses: tuple[PairwiseHypothesisV3, ...] = ()


class FailurePolicyV3(StrictModel):
    analysis_population: Literal["hidden_test_90_intention_to_evaluate"]
    missing_higher_is_better_score: float
    failure_higher_is_better_score: float
    missing_lower_is_better_score: float
    failure_lower_is_better_score: float
    complete_case_analysis: Literal["sensitivity_only_cannot_rescue"]
    invalid_intermediate_policy: Literal["terminal_system_failure_no_repair"]
    contrast_failure_policy: Literal["one_sided_lower_support_two_sided_null"]

    @model_validator(mode="after")
    def validate_scores(self) -> FailurePolicyV3:
        if (
            self.missing_higher_is_better_score,
            self.failure_higher_is_better_score,
            self.missing_lower_is_better_score,
            self.failure_lower_is_better_score,
        ) != (0.0, 0.0, 1.0, 1.0):
            raise ValueError("failure scores must use the frozen worst-case policy")
        return self


class MediationDiagnosticV3(StrictModel):
    status: Literal["preregistered_secondary_not_causal_identification"]
    mediator_id: Literal["stage_one_process_accuracy"]
    mediator_definition: Literal[
        "macro_mean_of_decision_required_fact_branch_and_terminal_recall_against_generator_state"
    ]
    missing_or_failure_score: float
    exposure_contrast: Literal["ORDER_MAIN"]
    outcome_endpoints: tuple[EndpointIdV3, ...]
    estimator: Literal[
        "family_cluster_weighted_product_of_order_to_mediator_and_adjusted_mediator_to_outcome_coefficients"
    ]
    adjustment_terms: tuple[
        Literal["order", "representation", "order_x_representation", "domain"], ...
    ]
    uncertainty: Literal["delete_one_family_jackknife_interval"]
    interpretation: Literal[
        "mechanism_consistency_only_post_treatment_mediator_assumptions_preclude_causal_claim"
    ]


class CustomFloorV3(StrictModel):
    endpoint_id: EndpointIdV3
    direction: Literal["higher", "lower"]
    threshold: float = Field(ge=0.0, le=1.0)


class AntiCircularControlsV3(StrictModel):
    heuristic_baseline: Literal[
        "deterministic_alias_overlap_plus_generic_policy_rule_traversal_zero_model_calls"
    ]
    heuristic_model_calls: Literal[0]
    heuristic_role: Literal["anti_circular_floor_not_headline_competitor"]
    ontology_perturbation_status: Literal["deferred_requires_new_protocol_version"]
    ontology_perturbation_calls_authorized: Literal[False]
    ontology_invariance_claim_allowed: Literal[False]
    deferral_reason: Literal[
        "no_matched_budget_schedule_runner_outcome_grid_and_analysis_in_primary_publication_v3"
    ]
    future_claim_rule: Literal[
        "new_locked_budgeted_canaried_protocol_required_before_any_ontology_invariance_claim"
    ]


class SecondBackboneReplicationV3(StrictModel):
    status_at_protocol_freeze: Literal[
        "optional_post_primary_replication_requires_new_locked_protocol"
    ]
    primary_backbone: Literal["nvidia/nemotron-3-ultra-550b-a55b"]
    primary_protocol_scope: Literal["nemotron_only"]
    replication_role: Literal["optional_robustness_not_required_for_primary_claim"]
    scope: Literal["zero_secondary_model_rows_in_primary_publication_v3"]
    production_calls_authorized: Literal[False]
    new_protocol_version_required: Literal[True]
    new_budget_required: Literal[True]
    new_route_canary_required: Literal[True]
    new_analysis_lock_required: Literal[True]
    claim_rule: Literal[
        "no_cross_backbone_claim_without_separately_locked_budgeted_canaried_and_completed_replication"
    ]
    required_final_lock_field: Literal["secondary_model_decision_sha256"]


class ReleaseDecisionV3(StrictModel):
    contract: Literal["casepath.custom-release-decision/3.0.0"]
    artifact_name: Literal["CasePath-Bench-v3"]
    preserved_internal_corpus: Literal["private-candidate-corpus-v2-final-2"]
    preserved_internal_corpus_reuse: Literal[
        "source_rows_repackaged_only_under_new_user_granted_public_manifest"
    ]
    target_source_contract: Literal["casepath.public-benchmark-corpus/3.0.0"]
    release_status: Literal["blocked_requires_release_packaging", "release_ready"]
    user_distribution_grant_recorded: Literal[True]
    clean_room_generation_required: Literal[False]
    data_license: Literal["CC-BY-4.0"]
    code_license: Literal["Apache-2.0"]
    paper_role: Literal["coprimary_after_release_gate"]
    headline_eligible: bool
    required_receipts: tuple[
        Literal[
            "synthetic_provenance",
            "content_hashes",
            "no_hidden_label_leakage",
            "group_safe_split",
            "grounding_locator",
            "independent_compiler",
            "independent_reference_evaluator",
            "reproducibility",
            "leaderboard_anti_gaming",
        ],
        ...,
    ]
    release_manifest_sha256: Sha256 | None = None
    release_gate_receipt_sha256: Sha256 | None = None
    blockers: tuple[str, ...]
    decision_sha256: Sha256

    @model_validator(mode="after")
    def validate_decision(self) -> ReleaseDecisionV3:
        expected_receipts = {
            "synthetic_provenance",
            "content_hashes",
            "no_hidden_label_leakage",
            "group_safe_split",
            "grounding_locator",
            "independent_compiler",
            "independent_reference_evaluator",
            "reproducibility",
            "leaderboard_anti_gaming",
        }
        if set(self.required_receipts) != expected_receipts:
            raise ValueError("public benchmark release decision omits a required receipt")
        ready = self.release_status == "release_ready"
        if ready != self.headline_eligible:
            raise ValueError("only a release-ready benchmark may be headline eligible")
        if ready:
            if not self.release_manifest_sha256 or not self.release_gate_receipt_sha256:
                raise ValueError("release-ready decision requires manifest and gate receipts")
            if self.blockers:
                raise ValueError("release-ready decision cannot retain blockers")
        elif (
            self.release_manifest_sha256 is not None
            or self.release_gate_receipt_sha256 is not None
            or not self.blockers
        ):
            raise ValueError("blocked release decision must name unresolved work only")
        expected = digest_json(self.model_dump(mode="json", exclude={"decision_sha256"}))
        if self.decision_sha256 != expected:
            raise ValueError("custom release decision hash is stale")
        return self


class CustomFactorialProtocolV3(StrictModel):
    contract: Literal["casepath.custom-factorial-protocol/3.0.0"]
    protocol_id: Literal["casepath-bench-public-factorial-v3"]
    status: Literal["specified_requires_release_ready_gate"]
    supersedes: tuple[
        Literal["casepath.prompt-bundle/0.1.0"],
        Literal["casepath.publication-protocol/2.1.0"],
    ]
    old_lock_compatibility: Literal["prohibited"]
    scientific_role: Literal["public_benchmark_coprimary_after_release_gate"]
    paper_evidence_priority: Literal["casepath_benchmark_and_public_native_coprimary"]
    release_decision_sha256: Sha256
    case_count: Literal[150]
    family_count: Literal[28]
    domain_family_counts: dict[DomainV3, int]
    split_policy: Literal["whole_family_public_dev_60_hidden_test_90"]
    public_dev_case_count: Literal[60]
    hidden_test_case_count: Literal[90]
    public_dev_domain_family_counts: dict[DomainV3, int]
    hidden_test_domain_family_counts: dict[DomainV3, int]
    primary_model: Literal["nvidia/nemotron-3-ultra-550b-a55b"]
    factorial_cells: tuple[FactorialCellV3, ...] = Field(min_length=4, max_length=4)
    separate_generative_falsification: Literal["EXIDE_V3"]
    document_first_falsification: Literal["DOCUMENT_FIRST_V3"]
    deterministic_verifier: Literal["VERIFY_PF_TYPED_V3"]
    verifier_source: Literal["PF_TYPED_V3"]
    heuristic_baseline: Literal["ONTOLOGY_RULE_HEURISTIC_V3"]
    calls_per_generative_condition: Literal[2]
    generative_condition_count: Literal[6]
    total_call_ceiling: Literal[1800]
    tool_calls_per_condition: Literal[0]
    retrieval_bytes_per_condition: Literal[0]
    prompt_matching_rule: Literal[
        "model_hidden_condition_ids_shared_bytes_except_declared_factor_slots_and_response_representation_schema"
    ]
    schedule_design: Literal["six_sequence_williams_six_conditions_twenty_five_complete_blocks"]
    schedule_counts: dict[str, Literal[25]]
    contrasts: tuple[FactorialContrastV3, ...] = Field(min_length=3, max_length=3)
    multiplicity_families: tuple[MultiplicityFamilyV3, ...] = Field(min_length=5, max_length=5)
    headline_operator: Literal["all_four_order_main_endpoint_hypotheses_pass"]
    absolute_floor_condition: Literal["PF_TYPED_V3"]
    absolute_floor_scope: Literal["pooled_and_each_domain"]
    absolute_floor_interval: Literal["two_sided_95_family_cluster_t"]
    absolute_floors: tuple[CustomFloorV3, ...] = Field(min_length=11, max_length=11)
    missing_and_failure: FailurePolicyV3
    mediator: MediationDiagnosticV3
    anti_circular_controls: AntiCircularControlsV3
    second_backbone: SecondBackboneReplicationV3
    estimator: Literal[
        "within_case_contrast_then_equal_case_within_family_equal_family_within_domain_equal_domain_cluster_t_satterthwaite"
    ]
    simulation_requirement: Literal[
        "exact_hidden_test_90_case_17_family_factorial_null_fwer_coverage_power_and_missingness_before_lock"
    ]
    experts_required: Literal[False]
    protocol_sha256: Sha256

    @model_validator(mode="after")
    def validate_protocol(self) -> CustomFactorialProtocolV3:
        cells = {
            (cell.order, cell.representation): cell.condition_id for cell in self.factorial_cells
        }
        if cells != {
            ("process_first", "typed"): "PF_TYPED_V3",
            ("process_first", "plain_text"): "PF_PLAIN_V3",
            ("direct_neutral", "typed"): "DIRECT_TYPED_V3",
            ("direct_neutral", "plain_text"): "DIRECT_PLAIN_V3",
        }:
            raise ValueError("factorial cells do not form the frozen 2x2 design")
        if self.domain_family_counts != {
            "defect_mold_heating": 10,
            "lease_termination_dispute": 8,
            "rent_increase_dispute": 10,
        }:
            raise ValueError("public benchmark must preserve the exact 10/8/10 source families")
        if self.public_dev_domain_family_counts != {
            "defect_mold_heating": 4,
            "lease_termination_dispute": 3,
            "rent_increase_dispute": 4,
        } or self.hidden_test_domain_family_counts != {
            "defect_mold_heating": 6,
            "lease_termination_dispute": 5,
            "rent_increase_dispute": 6,
        }:
            raise ValueError("public dev/test family geometry must be 4/3/4 and 6/5/6")
        if self.schedule_counts != {f"F{index:02d}": 25 for index in range(1, 7)}:
            raise ValueError("150 cases must form twenty-five complete six-sequence blocks")
        if {item.contrast_id for item in self.contrasts} != {
            "ORDER_MAIN",
            "REPRESENTATION_MAIN",
            "ORDER_X_REPRESENTATION",
        }:
            raise ValueError("factorial protocol must freeze all three factorial contrasts")
        families = {family.family_id: family for family in self.multiplicity_families}
        if set(families) != {
            "order_headline",
            "factorial_mechanism",
            "verifier_falsification",
            "exide_falsification",
            "document_first_falsification",
        }:
            raise ValueError("custom protocol has the wrong multiplicity families")
        headline = families["order_headline"]
        if (
            not headline.required_for_benchmark_order_claim
            or headline.familywise_alpha != 0.04
            or headline.pairwise_hypotheses
            or len(headline.factorial_hypotheses) != 4
        ):
            raise ValueError("exactly four order-main tests must control the benchmark claim")
        observed_headline = {
            (
                item.contrast_id,
                item.endpoint_id,
                item.benefit_direction,
                item.decision_rule,
                item.margin,
            )
            for item in headline.factorial_hypotheses
        }
        if observed_headline != {
            ("ORDER_MAIN", "behavioral_valid_path_rate", "higher", "superiority", 0.03),
            ("ORDER_MAIN", "branch_predicate_accuracy", "higher", "superiority", 0.03),
            ("ORDER_MAIN", "critical_evidence_recall", "higher", "superiority", 0.03),
            (
                "ORDER_MAIN",
                "unnecessary_document_rate",
                "lower",
                "noninferiority",
                0.03,
            ),
        }:
            raise ValueError("headline does not isolate the process-order main effect")
        if any(
            family.required_for_benchmark_order_claim
            for family_id, family in families.items()
            if family_id != "order_headline"
        ):
            raise ValueError("secondary and falsification tests cannot rescue the order claim")
        if any(
            family.familywise_alpha != 0.05
            for family_id, family in families.items()
            if family_id != "order_headline"
        ):
            raise ValueError("non-headline families must use Holm at 0.05")
        floors = {
            item.endpoint_id: (item.direction, item.threshold) for item in self.absolute_floors
        }
        if floors != {
            "behavioral_valid_path_rate": ("higher", 0.8),
            "branch_predicate_accuracy": ("higher", 0.8),
            "required_node_recall": ("higher", 0.8),
            "required_edge_recall": ("higher", 0.8),
            "critical_evidence_recall": ("higher", 0.8),
            "unnecessary_document_rate": ("lower", 0.2),
            "document_state_accuracy": ("higher", 0.8),
            "valid_chain_precision": ("higher", 0.8),
            "fact_chain_completeness": ("higher", 0.8),
            "evidence_obligation_completeness": ("higher", 0.8),
            "source_grounding_exactness": ("higher", 1.0),
        }:
            raise ValueError("custom absolute floors differ from the frozen 80/20/exact policy")
        if set(self.mediator.outcome_endpoints) != {
            "critical_evidence_recall",
            "unnecessary_document_rate",
            "valid_chain_precision",
            "fact_chain_completeness",
            "evidence_obligation_completeness",
        }:
            raise ValueError("mediation diagnostic must cover the five evidence-planning endpoints")
        if self.mediator.missing_or_failure_score != 0.0:
            raise ValueError("mediation failures must receive the frozen zero score")
        expected = digest_json(self.model_dump(mode="json", exclude={"protocol_sha256"}))
        if self.protocol_sha256 != expected:
            raise ValueError("custom factorial protocol hash is stale")
        return self


class SecondaryModelDecisionV3(StrictModel):
    """Outcome-blind record that keeps secondary replication outside the primary lock."""

    contract: Literal["casepath.secondary-model-decision/3.0.0"]
    decision_status: Literal["deferred_requires_new_protocol_version"]
    primary_protocol_scope: Literal["nemotron_only"]
    selected_model_id: None
    selected_provider_route: None
    selected_case_ids: tuple[()] = ()
    selection_rule: Literal["no_secondary_model_selected_in_publication_v3"]
    selection_made_before_primary_outcomes: Literal[True]
    primary_outcomes_accessed: Literal[False]
    production_calls_authorized: Literal[False]
    new_protocol_version_required: Literal[True]
    directional_replication_claim_allowed: Literal[False]
    deferral_reason: Literal[
        "no_complete_matched_route_budget_canary_runner_and_analysis_existed_at_primary_freeze"
    ]
    decision_sha256: Sha256

    @model_validator(mode="after")
    def validate_decision(self) -> SecondaryModelDecisionV3:
        if self.selected_case_ids:
            raise ValueError("deferred secondary replication cannot select outcome rows")
        expected = digest_json(self.model_dump(mode="json", exclude={"decision_sha256"}))
        if self.decision_sha256 != expected:
            raise ValueError("secondary-model decision hash is stale")
        return self


class OntologyPerturbationReceiptV3(StrictModel):
    contract: Literal["casepath.ontology-perturbation/3.0.0"]
    case_id: str = Field(min_length=1)
    source_ontology_sha256: Sha256
    perturbed_ontology_sha256: Sha256
    perturbation: Literal[
        "opaque_symbols_with_semantics_preserved_in_rewritten_public_rules_plus_case_keyed_order"
    ]
    label_mapping_sha256: Sha256
    predicate_mapping_sha256: Sha256
    reversible: Literal[True]
    hidden_oracle_used: Literal[False]
    receipt_sha256: Sha256

    @model_validator(mode="after")
    def validate_receipt(self) -> OntologyPerturbationReceiptV3:
        expected = digest_json(self.model_dump(mode="json", exclude={"receipt_sha256"}))
        if self.receipt_sha256 != expected:
            raise ValueError("ontology perturbation receipt hash is stale")
        return self


class PublicBenchmarkCaseV3(StrictModel):
    case_id: str = Field(min_length=1)
    domain: DomainV3
    language: Literal["de-CH", "en"]
    family_id: str = Field(pattern=r"^ndg_[0-9a-f]{20}$")
    split: Literal["public_dev", "hidden_test"]
    observable_claim_path: str = Field(pattern=r"^data/(dev|test)/claims/[A-Za-z0-9._-]+\.json$")
    source_registry_path: str = Field(
        pattern=r"^data/(dev|test)/source-registry/[A-Za-z0-9._-]+\.json$"
    )
    source_document_paths: tuple[str, ...] = Field(min_length=1)
    public_gold_path: str | None = None
    hidden_contract_commitment_sha256: Sha256 | None = None
    row_sha256: Sha256

    @model_validator(mode="after")
    def validate_visibility(self) -> PublicBenchmarkCaseV3:
        expected_zone = "dev" if self.split == "public_dev" else "test"
        source_pattern = re.compile(
            rf"^data/{expected_zone}/sources/[A-Za-z0-9._-]+/"
            rf"[A-Za-z0-9._-]+\.(?:txt|eml|pdf|jpg|jpeg|png)$"
        )
        if (
            not self.observable_claim_path.startswith(f"data/{expected_zone}/claims/")
            or not self.source_registry_path.startswith(f"data/{expected_zone}/source-registry/")
            or len(set(self.source_document_paths)) != len(self.source_document_paths)
            or any(source_pattern.fullmatch(path) is None for path in self.source_document_paths)
        ):
            raise ValueError("source document paths repeat or escape their split")
        if self.split == "public_dev":
            if self.public_gold_path is None or self.hidden_contract_commitment_sha256 is not None:
                raise ValueError("public dev cases require gold and cannot use hidden commitments")
            if not re.fullmatch(r"data/dev/gold/[A-Za-z0-9._-]+\.json", self.public_gold_path):
                raise ValueError("public dev gold path is outside the release package")
        elif self.public_gold_path is not None or self.hidden_contract_commitment_sha256 is None:
            raise ValueError("hidden test cases expose only evaluator commitments")
        expected = digest_json(self.model_dump(mode="json", exclude={"row_sha256"}))
        if self.row_sha256 != expected:
            raise ValueError("public benchmark case hash is stale")
        return self


class PublicBenchmarkFileV3(StrictModel):
    relative_path: str = Field(min_length=1)
    file_sha256: Sha256
    size_bytes: int = Field(gt=0)
    role: Literal[
        "observable_claim",
        "source_registry",
        "source_document",
        "public_dev_gold",
        "schema",
        "metric_code",
        "baseline_code",
        "documentation",
    ]
    grounding_locator_count: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_safe_relative_path(self) -> PublicBenchmarkFileV3:
        path = PurePosixPath(self.relative_path)
        if (
            path.is_absolute()
            or "\\" in self.relative_path
            or any(part in {"", ".", ".."} for part in path.parts)
        ):
            raise ValueError("public benchmark file path is unsafe")
        return self


class PublicBenchmarkManifestV3(StrictModel):
    contract: Literal["casepath.public-benchmark-corpus/3.0.0"]
    benchmark_id: Literal["casepath-bench-v3"]
    data_license: Literal["CC-BY-4.0"]
    code_license: Literal["Apache-2.0"]
    source_corpus_identity: Literal["private-candidate-corpus-v2-final-2"]
    source_manifest_flags_superseded_by: Literal[
        "explicit_user_distribution_grant_and_new_v3_release_receipt"
    ]
    synthetic_data_declaration: Literal["fully_synthetic_no_real_personal_data_by_construction"]
    user_distribution_grant_recorded: Literal[True]
    public_model_policy: Literal[
        "all_three_static_domain_rule_templates_identical_for_every_case_no_hidden_routing"
    ]
    public_task_scope: Literal[
        "closed_vocabulary_domain_selection_case_specific_structure_activation_and_evidence_planning"
    ]
    open_vocabulary_discovery_evidence_source: Literal["PAGED_native_benchmark"]
    cases: tuple[PublicBenchmarkCaseV3, ...] = Field(min_length=150, max_length=150)
    files: tuple[PublicBenchmarkFileV3, ...] = Field(min_length=1)
    dev_gold_public: Literal[True]
    test_contracts_public: Literal[False]
    hidden_test_contract_bundle_sha256: Sha256
    evaluator_bundle_sha256: Sha256
    evaluator_api_contract: Literal["casepath.leaderboard-evaluator/3.0.0"]
    state_stress_manifest_sha256: Sha256
    state_stress_variant_count: Literal[48]
    state_stress_public_dev_gold: Literal[True]
    independent_compiler_sha256: Sha256
    independent_reference_evaluator_sha256: Sha256
    metric_code_sha256: Sha256
    baseline_bundle_sha256: Sha256
    reproducibility_bundle_sha256: Sha256
    leaderboard_policy_sha256: Sha256
    grounding_mutation_test_sha256: Sha256
    case_roster_sha256: Sha256
    file_set_sha256: Sha256
    manifest_sha256: Sha256

    @model_validator(mode="after")
    def validate_manifest(self) -> PublicBenchmarkManifestV3:
        case_ids = [case.case_id for case in self.cases]
        if len(set(case_ids)) != 150:
            raise ValueError("public benchmark requires 150 unique cases")
        split_counts = Counter(case.split for case in self.cases)
        if split_counts != Counter({"public_dev": 60, "hidden_test": 90}):
            raise ValueError("public benchmark split must be 60 dev and 90 hidden test")
        families_by_split = {
            split: {case.family_id for case in self.cases if case.split == split}
            for split in ("public_dev", "hidden_test")
        }
        if families_by_split["public_dev"] & families_by_split["hidden_test"]:
            raise ValueError("near-duplicate families cross public dev and hidden test")
        if (
            len(families_by_split["public_dev"]) != 11
            or len(families_by_split["hidden_test"]) != 17
        ):
            raise ValueError("public dev/test must contain 11/17 complete families")
        for split, cases, language_count in (("public_dev", 60, 30), ("hidden_test", 90, 45)):
            rows = [case for case in self.cases if case.split == split]
            if Counter(case.language for case in rows) != Counter(
                {"de-CH": language_count, "en": language_count}
            ):
                raise ValueError(f"{split} is not language balanced")
            if Counter(case.domain for case in rows) != Counter(
                {
                    "defect_mold_heating": cases // 3,
                    "lease_termination_dispute": cases // 3,
                    "rent_increase_dispute": cases // 3,
                }
            ):
                raise ValueError(f"{split} is not domain balanced")
        paths = [item.relative_path for item in self.files]
        if len(paths) != len(set(paths)):
            raise ValueError("release manifest contains duplicate file paths")
        released_paths = set(paths)
        for case in self.cases:
            required = {
                case.observable_claim_path,
                case.source_registry_path,
                *case.source_document_paths,
                *([case.public_gold_path] if case.public_gold_path else []),
            }
            if not required.issubset(released_paths):
                raise ValueError("a case references a file absent from the release manifest")
        roster = [case.model_dump(mode="json") for case in self.cases]
        if self.case_roster_sha256 != digest_json(roster):
            raise ValueError("public benchmark roster hash is stale")
        file_rows = [item.model_dump(mode="json") for item in self.files]
        if self.file_set_sha256 != digest_json(file_rows):
            raise ValueError("public benchmark file-set hash is stale")
        if self.manifest_sha256 != digest_json(
            self.model_dump(mode="json", exclude={"manifest_sha256"})
        ):
            raise ValueError("public benchmark manifest hash is stale")
        return self


class PublicBenchmarkReleaseGateV3(StrictModel):
    contract: Literal["casepath.public-benchmark-release-gate/3.0.0"]
    manifest_sha256: Sha256
    evaluated_case_count: Literal[150]
    public_dev_case_count: Literal[60]
    hidden_test_case_count: Literal[90]
    group_overlap_count: Literal[0]
    missing_file_count: Literal[0]
    hash_mismatch_count: Literal[0]
    missing_grounding_locator_count: Literal[0]
    source_registry_case_count: Literal[150]
    unresolved_registry_locator_count: Literal[0]
    forbidden_registry_key_count: Literal[0]
    gold_locator_not_visible_count: Literal[0]
    proposition_specific_traceability_passed: Literal[True]
    authority_passage_count: Literal[19]
    observable_message_span_count: Literal[2490]
    provenance_chain_expectation_count: Literal[1397]
    independent_traceability_value_count: Literal[600]
    independent_traceability_match_count: Literal[600]
    hidden_contract_exposure_count: Literal[0]
    independent_compiler_replay_passed: Literal[True]
    independent_reference_evaluator_replay_passed: Literal[True]
    independent_reported_endpoint_value_count: Literal[2100]
    independent_reported_endpoint_match_count: Literal[2100]
    independent_semantic_attack_attempt_count: Literal[1050]
    independent_semantic_attack_kill_count: Literal[1050]
    independent_grounding_attack_attempt_count: Literal[1050]
    independent_grounding_attack_kill_count: Literal[1050]
    reference_candidate_accepted_count: Literal[150]
    state_stress_manifest_valid: Literal[True]
    state_stress_variant_count: Literal[48]
    state_stress_reference_pass_count: Literal[48]
    reproducibility_smoke_passed: Literal[True]
    reproducibility_smoke_receipt_sha256: Sha256
    leaderboard_anti_gaming_tests_passed: Literal[True]
    semantic_mutation_attempt_count: Literal[1203]
    semantic_mutation_kill_count: Literal[1203]
    grounding_mutation_attempt_count: Literal[1050]
    grounding_mutation_kill_count: Literal[1050]
    empty_output_rejected_count: Literal[150]
    request_everything_rejected_count: Literal[150]
    semantic_audit_receipt_sha256: Sha256
    release_ready: Literal[True]
    receipt_sha256: Sha256

    @model_validator(mode="after")
    def validate_receipt(self) -> PublicBenchmarkReleaseGateV3:
        if self.receipt_sha256 != digest_json(
            self.model_dump(mode="json", exclude={"receipt_sha256"})
        ):
            raise ValueError("public benchmark release gate hash is stale")
        return self


class PublicBenchmarkCohortV3(StrictModel):
    contract: Literal["casepath.public-benchmark-cohort/3.0.0"]
    manifest_sha256: Sha256
    cases: tuple[PublicBenchmarkCaseV3, ...] = Field(min_length=150, max_length=150)
    cohort_sha256: Sha256

    @model_validator(mode="after")
    def validate_cohort(self) -> PublicBenchmarkCohortV3:
        case_ids = [case.case_id for case in self.cases]
        if len(set(case_ids)) != 150:
            raise ValueError("public benchmark cohort requires 150 unique cases")
        if Counter(case.split for case in self.cases) != Counter(
            {"public_dev": 60, "hidden_test": 90}
        ):
            raise ValueError("public benchmark cohort has the wrong split")
        if self.cohort_sha256 != digest_json(
            self.model_dump(mode="json", exclude={"cohort_sha256"})
        ):
            raise ValueError("public benchmark cohort hash is stale")
        return self


class CustomOutcomeV3(StrictModel):
    case_id: str = Field(min_length=1)
    condition: ConditionIdV3
    endpoint_id: EndpointIdV3
    status: Literal["observed", "missing", "system_failure"]
    value: float | None = None

    @model_validator(mode="after")
    def validate_value(self) -> CustomOutcomeV3:
        if (self.status == "observed") != (self.value is not None):
            raise ValueError("only observed outcomes may contain a value")
        if self.value is not None and not 0.0 <= self.value <= 1.0:
            raise ValueError("custom endpoint values must lie in [0, 1]")
        return self


class StageOneMediatorOutcomeV3(StrictModel):
    case_id: str = Field(min_length=1)
    condition: FactorialConditionIdV3
    mediator_id: Literal["stage_one_process_accuracy"]
    status: Literal["observed", "missing", "system_failure"]
    value: float | None = None

    @model_validator(mode="after")
    def validate_value(self) -> StageOneMediatorOutcomeV3:
        if (self.status == "observed") != (self.value is not None):
            raise ValueError("only observed mediator outcomes may contain a value")
        if self.value is not None and not 0.0 <= self.value <= 1.0:
            raise ValueError("stage-one process accuracy must lie in [0, 1]")
        return self


class CustomOutcomeBundleV3(StrictModel):
    contract: Literal["casepath.custom-factorial-outcomes/3.0.0"]
    publication_lock_sha256: Sha256
    custom_protocol_sha256: Sha256
    cohort_sha256: Sha256
    release_manifest_sha256: Sha256
    release_gate_receipt_sha256: Sha256
    evaluator_bundle_sha256: Sha256
    scorer_code_sha256: Sha256
    run_completeness_receipt_sha256: Sha256
    run_record_set_sha256: Sha256
    candidate_set_sha256: Sha256
    outcomes: tuple[CustomOutcomeV3, ...] = Field(min_length=13200, max_length=13200)
    mediator_outcomes: tuple[StageOneMediatorOutcomeV3, ...] = Field(min_length=600, max_length=600)
    bundle_sha256: Sha256

    @model_validator(mode="after")
    def validate_bundle(self) -> CustomOutcomeBundleV3:
        outcome_keys = [(item.case_id, item.condition, item.endpoint_id) for item in self.outcomes]
        mediator_keys = [
            (item.case_id, item.condition, item.mediator_id) for item in self.mediator_outcomes
        ]
        if len(set(outcome_keys)) != 13200:
            raise ValueError("custom outcome bundle has duplicate or missing final rows")
        if len(set(mediator_keys)) != 600:
            raise ValueError("custom outcome bundle has duplicate or missing mediator rows")
        if len({item.case_id for item in self.outcomes}) != 150:
            raise ValueError("custom outcomes do not cover 150 cases")
        expected = digest_json(self.model_dump(mode="json", exclude={"bundle_sha256"}))
        if self.bundle_sha256 != expected:
            raise ValueError("custom outcome bundle hash is stale")
        return self


class FactorialEstimateV3(StrictModel):
    hypothesis_id: str = Field(min_length=1)
    family_id: str = Field(min_length=1)
    effect_kind: Literal["factorial", "pairwise"]
    contrast_id: str = Field(min_length=1)
    endpoint_id: EndpointIdV3
    benefit_estimate: float
    confidence_lower: float
    confidence_upper: float
    raw_p_value: float = Field(ge=0.0, le=1.0)
    adjusted_p_value: float = Field(ge=0.0, le=1.0)
    margin: float = Field(ge=0.0)
    decision_rule: Literal["superiority", "noninferiority", "two_sided_interaction"]
    margin_passed: bool
    multiplicity_passed: bool
    passed: bool
    analyzed_cases: Literal[90]
    analyzed_families: Literal[17]
    analyzed_domains: Literal[3]

    @model_validator(mode="after")
    def validate_estimate(self) -> FactorialEstimateV3:
        if not self.confidence_lower <= self.benefit_estimate <= self.confidence_upper:
            raise ValueError("factorial estimate must lie inside its interval")
        if self.passed != (self.margin_passed and self.multiplicity_passed):
            raise ValueError("factorial decision fields disagree")
        return self


class AbsoluteFloorResultV3(StrictModel):
    condition: Literal["PF_TYPED_V3"]
    endpoint_id: EndpointIdV3
    scope: Literal[
        "pooled",
        "defect_mold_heating",
        "lease_termination_dispute",
        "rent_increase_dispute",
    ]
    direction: Literal["higher", "lower"]
    threshold: float = Field(ge=0.0, le=1.0)
    estimate: float
    confidence_lower: float
    confidence_upper: float
    passed: bool


class MediationResultV3(StrictModel):
    endpoint_id: EndpointIdV3
    estimable: bool
    order_to_mediator: float | None = None
    adjusted_mediator_to_outcome: float | None = None
    product_estimate: float | None = None
    jackknife_lower: float | None = None
    jackknife_upper: float | None = None
    family_deletions: Literal[17]
    nonestimable_reason: Literal["zero_mediator_variance_or_singular_design"] | None = None
    interpretation: Literal["mechanism_consistency_only_not_causal"]

    @model_validator(mode="after")
    def validate_estimability(self) -> MediationResultV3:
        statistics = (
            self.order_to_mediator,
            self.adjusted_mediator_to_outcome,
            self.product_estimate,
            self.jackknife_lower,
            self.jackknife_upper,
        )
        if self.estimable != all(item is not None for item in statistics):
            raise ValueError("mediation estimability and statistics disagree")
        if self.estimable == (self.nonestimable_reason is not None):
            raise ValueError("mediation nonestimable reason is inconsistent")
        if self.estimable:
            assert self.order_to_mediator is not None
            assert self.adjusted_mediator_to_outcome is not None
            assert self.product_estimate is not None
            assert self.jackknife_lower is not None
            assert self.jackknife_upper is not None
            if not math.isclose(
                self.product_estimate,
                self.order_to_mediator * self.adjusted_mediator_to_outcome,
                rel_tol=1e-12,
                abs_tol=1e-12,
            ):
                raise ValueError("mediation product is inconsistent")
            if not self.jackknife_lower <= self.product_estimate <= self.jackknife_upper:
                raise ValueError("mediation estimate lies outside its jackknife interval")
        return self


class CompleteCaseSensitivityV3(StrictModel):
    hypothesis_id: str = Field(min_length=1)
    family_id: str = Field(min_length=1)
    complete_case_count: int = Field(ge=0, le=90)
    complete_family_count: int = Field(ge=0, le=17)
    complete_domain_count: int = Field(ge=0, le=3)
    estimable: bool
    benefit_estimate: float | None = None
    confidence_lower: float | None = None
    confidence_upper: float | None = None
    raw_p_value: float | None = Field(default=None, ge=0.0, le=1.0)
    adjusted_p_value: float | None = Field(default=None, ge=0.0, le=1.0)
    role: Literal["sensitivity_only_cannot_rescue"]

    @model_validator(mode="after")
    def validate_sensitivity(self) -> CompleteCaseSensitivityV3:
        statistics = (
            self.benefit_estimate,
            self.confidence_lower,
            self.confidence_upper,
            self.raw_p_value,
            self.adjusted_p_value,
        )
        if self.estimable != all(value is not None for value in statistics):
            raise ValueError("complete-case estimability and statistics disagree")
        if self.estimable:
            assert self.benefit_estimate is not None
            assert self.confidence_lower is not None
            assert self.confidence_upper is not None
            if not self.confidence_lower <= self.benefit_estimate <= self.confidence_upper:
                raise ValueError("complete-case estimate must lie inside its interval")
            if (
                self.complete_case_count == 0
                or self.complete_family_count == 0
                or self.complete_domain_count == 0
            ):
                raise ValueError("estimable complete-case result requires retained observations")
        elif any(value is not None for value in statistics):
            raise ValueError("inestimable complete-case result cannot contain statistics")
        return self


class CustomFactorialAnalysisReceiptV3(StrictModel):
    contract: Literal["casepath.custom-factorial-analysis/3.0.0"]
    publication_lock_sha256: Sha256
    custom_protocol_sha256: Sha256
    cohort_sha256: Sha256
    outcome_bundle_sha256: Sha256
    release_manifest_sha256: Sha256
    release_gate_receipt_sha256: Sha256
    evaluator_bundle_sha256: Sha256
    scorer_code_sha256: Sha256
    run_completeness_receipt_sha256: Sha256
    estimates: tuple[FactorialEstimateV3, ...] = Field(min_length=40, max_length=40)
    absolute_floor_results: tuple[AbsoluteFloorResultV3, ...] = Field(min_length=44, max_length=44)
    mediation_results: tuple[MediationResultV3, ...] = Field(min_length=5, max_length=5)
    complete_case_sensitivity: tuple[CompleteCaseSensitivityV3, ...] = Field(
        min_length=40, max_length=40
    )
    complete_case_sensitivity_reported: Literal[True]
    complete_case_can_rescue: Literal[False]
    benchmark_order_claim_passed: bool
    absolute_quality_passed: bool
    benchmark_coprimary_passed: bool
    paper_headline_eligible: bool
    paper_role: Literal["casepath_benchmark_coprimary"]
    public_native_results_required_for_full_paper_claim: Literal[True]
    human_evidence_used: Literal[False]
    receipt_sha256: Sha256

    @model_validator(mode="after")
    def validate_receipt(self) -> CustomFactorialAnalysisReceiptV3:
        estimates = {item.hypothesis_id: item for item in self.estimates}
        if len(estimates) != len(self.estimates):
            raise ValueError("analysis receipt contains duplicate estimates")
        sensitivity_ids = {item.hypothesis_id for item in self.complete_case_sensitivity}
        if sensitivity_ids != set(estimates):
            raise ValueError("complete-case sensitivity does not match the 40 hypotheses")
        benchmark_order = all(
            estimates[hypothesis].passed
            for hypothesis in (
                "H-ORDER-PATH",
                "H-ORDER-BRANCH",
                "H-ORDER-CER",
                "H-ORDER-UDR",
            )
        )
        absolute = all(item.passed for item in self.absolute_floor_results)
        if self.benchmark_order_claim_passed != benchmark_order:
            raise ValueError("benchmark order decision is stale")
        if self.absolute_quality_passed != absolute:
            raise ValueError("absolute-quality decision is stale")
        if self.benchmark_coprimary_passed != (benchmark_order and absolute):
            raise ValueError("benchmark coprimary decision is stale")
        if self.paper_headline_eligible != self.benchmark_coprimary_passed:
            raise ValueError("custom paper eligibility must follow the locked custom decision")
        expected = digest_json(self.model_dump(mode="json", exclude={"receipt_sha256"}))
        if self.receipt_sha256 != expected:
            raise ValueError("custom factorial analysis receipt hash is stale")
        return self
