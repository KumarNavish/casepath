"""Fail-closed contracts for the autonomous 150-case publication protocol.

Protocol v2 is a new study.  It does not reinterpret or modify confirmatory-v1.
The custom benchmark uses executable hidden state as its authority; optional
human observations can only be reported as a separate extension.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field, model_validator

from manifests.digests import digest_json

from .schema import StrictModel

Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
DomainV2 = Literal[
    "defect_mold_heating",
    "lease_termination_dispute",
    "rent_increase_dispute",
]
LanguageV2 = Literal["de-CH", "en"]
ConditionV2 = Literal["B3", "B6", "B7", "B8", "B9"]
EndpointV2 = Literal[
    "critical_evidence_recall",
    "unnecessary_document_rate",
    "valid_chain_precision",
    "fact_chain_completeness",
    "evidence_obligation_completeness",
]
DecisionRuleV2 = Literal["superiority", "noninferiority", "equivalence"]


class LockedCorpusIdentityV2(StrictModel):
    snapshot_id: Literal["private-candidate-corpus-v2-final-2"]
    source_contract: Literal["casepath.private-candidate-corpus/2.0.0"]
    source_manifest_name: Literal["corpus-manifest.json"]
    source_manifest_file_sha256: Literal[
        "aa0531f921342c5c19b22611a9ab3d2705939ddc02cbb321e2da5f3def349f7f"
    ]
    source_corpus_sha256: Literal[
        "84d827d30c8688c3e0ccfc71d89a3d64e96048eb2d2e43c32dd719a54209e966"
    ]
    source_plan_sha256: Literal["2d307a2ca424a94bf1f8e6529bfa40fdccfbd5e4d593072ec36fd19dbe5df782"]
    source_ledger_sha256: Literal[
        "66826c5b6b18acb29fff184dded4f9cbbbcc221bd5540caa7973d733bfdefc45"
    ]
    case_roster_sha256: Literal["d97a4d7c6cd0deb1fca4e933b0f85051f79fb9811d3949391dd47d093e566e1c"]
    family_roster_sha256: Literal[
        "2719537650821557084bafb41c99a6d1b3ee40ce39149196a97d7d057762bb8f"
    ]
    evaluation_case_count: Literal[150]
    domain_case_counts: dict[DomainV2, Literal[50]]
    language_case_counts: dict[LanguageV2, Literal[75]]
    family_count: Literal[28]
    domain_family_counts: dict[DomainV2, int]
    ground_truth_kind: Literal["deterministic_generator_hidden_state"]
    independent_human_review_status: Literal["not_performed"]

    @model_validator(mode="after")
    def validate_fixed_distribution(self) -> LockedCorpusIdentityV2:
        if self.domain_case_counts != {
            "defect_mold_heating": 50,
            "lease_termination_dispute": 50,
            "rent_increase_dispute": 50,
        }:
            raise ValueError("v2-final-2 must contain 50 cases in each actual domain")
        if self.language_case_counts != {"de-CH": 75, "en": 75}:
            raise ValueError("v2-final-2 must contain 75 cases in each language")
        if self.domain_family_counts != {
            "defect_mold_heating": 10,
            "lease_termination_dispute": 8,
            "rent_increase_dispute": 10,
        }:
            raise ValueError("v2-final-2 family counts differ from the locked 10/8/10 split")
        return self


class CaseFamilyBindingV2(StrictModel):
    case_id: str = Field(min_length=1)
    domain: DomainV2
    language: LanguageV2
    near_duplicate_group_id: str = Field(pattern=r"^ndg_[0-9a-f]{20}$")
    scenario_template_id: str = Field(min_length=1)
    row_receipt_sha256: Sha256
    role: Literal["evaluation"]


class LockedCohortV2(StrictModel):
    cohort_version: Literal["casepath.publication-cohort/2.0.0"]
    cohort_id: Literal["casepath-publication-v2-final-2-all-150"]
    source_manifest_file_sha256: Sha256
    source_corpus_sha256: Sha256
    cases: tuple[CaseFamilyBindingV2, ...] = Field(min_length=150, max_length=150)
    prompt_development_family_ids: tuple[str, ...] = ()
    evaluation_family_ids: tuple[str, ...] = Field(min_length=28, max_length=28)
    case_roster_sha256: Sha256
    family_roster_sha256: Sha256
    cohort_sha256: Sha256

    @model_validator(mode="after")
    def validate_cohort(self) -> LockedCohortV2:
        case_ids = [case.case_id for case in self.cases]
        if len(set(case_ids)) != 150:
            raise ValueError("publication v2 requires 150 unique evaluation cases")
        if Counter(case.domain for case in self.cases) != Counter(
            {
                "defect_mold_heating": 50,
                "lease_termination_dispute": 50,
                "rent_increase_dispute": 50,
            }
        ):
            raise ValueError("publication cohort does not contain the exact three 50-case domains")
        if Counter(case.language for case in self.cases) != Counter({"de-CH": 75, "en": 75}):
            raise ValueError("publication cohort is not language balanced")

        groups: dict[str, tuple[DomainV2, str]] = {}
        scenario_to_group: dict[str, str] = {}
        for case in self.cases:
            signature = (case.domain, case.scenario_template_id)
            previous = groups.setdefault(case.near_duplicate_group_id, signature)
            if previous != signature:
                raise ValueError("a near-duplicate family crosses domain or scenario template")
            old_group = scenario_to_group.setdefault(
                case.scenario_template_id, case.near_duplicate_group_id
            )
            if old_group != case.near_duplicate_group_id:
                raise ValueError("a scenario template maps to multiple near-duplicate families")
        if len(groups) != 28 or len(scenario_to_group) != 28:
            raise ValueError("publication cohort must contain exactly 28 paired family clusters")

        evaluation_families = tuple(sorted(groups))
        if self.evaluation_family_ids != evaluation_families:
            raise ValueError("evaluation family IDs must be the sorted cohort family set")
        if self.prompt_development_family_ids:
            raise ValueError("the locked 150-case corpus cannot be used for prompt development")
        if set(self.prompt_development_family_ids).intersection(evaluation_families):
            raise ValueError("a family cannot cross prompt development and evaluation")

        roster = [
            {
                "case_id": case.case_id,
                "domain": case.domain,
                "language": case.language,
                "near_duplicate_group_id": case.near_duplicate_group_id,
                "scenario_template_id": case.scenario_template_id,
                "row_receipt_sha256": case.row_receipt_sha256,
            }
            for case in self.cases
        ]
        if self.case_roster_sha256 != digest_json(roster):
            raise ValueError("publication case roster hash is stale")
        families = [
            {
                "domain": domain,
                "near_duplicate_group_id": group_id,
                "scenario_template_id": scenario_id,
            }
            for group_id, (domain, scenario_id) in sorted(groups.items())
        ]
        families.sort(
            key=lambda item: (
                item["domain"],
                item["near_duplicate_group_id"],
                item["scenario_template_id"],
            )
        )
        if self.family_roster_sha256 != digest_json(families):
            raise ValueError("publication family roster hash is stale")
        if self.cohort_sha256 != digest_json(
            self.model_dump(mode="json", exclude={"cohort_sha256"})
        ):
            raise ValueError("publication cohort hash is stale")
        return self


class AutonomousEndpointSpecV2(StrictModel):
    endpoint_id: EndpointV2
    source: Literal["autonomous_executable_oracle"]
    unit: Literal["proportion"]
    direction: Literal["higher", "lower"]
    minimum: float = Field(ge=0.0, le=0.0)
    maximum: float = Field(ge=1.0, le=1.0)
    missing_score: float
    system_failure_score: float
    definition: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_conservative_failure_score(self) -> AutonomousEndpointSpecV2:
        worst = 0.0 if self.direction == "higher" else 1.0
        if self.missing_score != worst or self.system_failure_score != worst:
            raise ValueError("missing and system-failure outcomes must receive the worst score")
        return self


class GroupAwareEstimandV2(StrictModel):
    estimand_id: Literal["equal-domain-family-case-macro-paired-benefit"]
    case_pairing: Literal["within_case_across_conditions"]
    case_weight_within_family: Literal["equal"]
    family_weight_within_domain: Literal["equal"]
    domain_weight: Literal["equal_one_third"]
    cluster_key: Literal["near_duplicate_group_id"]
    stratum_key: Literal["domain"]
    language_policy: Literal["pooled_primary_report_stratified_secondary"]
    interval_method: Literal["stratified_family_cluster_t_satterthwaite"]
    variance_method: Literal["independent_domain_cluster_means"]
    small_sample_degrees_of_freedom: Literal["welch_satterthwaite"]
    jackknife_unit: Literal["delete_one_family_sensitivity_only"]
    resamples: Literal[0]
    confidence_level: float = Field(ge=0.95, le=0.95)
    random_seed: Literal[27012027]
    p_value_method: Literal["one_sided_stratified_family_cluster_t"]


class HypothesisSpecV2(StrictModel):
    hypothesis_id: str = Field(min_length=1)
    treatment: ConditionV2
    control: ConditionV2
    endpoint_id: EndpointV2
    decision_rule: DecisionRuleV2
    margin: float = Field(ge=0.0)


class MultiplicityFamilyV2(StrictModel):
    family_id: Literal[
        "custom_headline",
        "mechanism_secondary",
        "b8_verifier_falsification",
        "b9_novelty_falsification",
    ]
    role: Literal["headline", "secondary_mechanism", "falsification"]
    required_for_headline: bool
    correction: Literal["holm"]
    familywise_alpha: float = Field(ge=0.04, le=0.05)
    hypotheses: tuple[HypothesisSpecV2, ...] = Field(min_length=1)


class SeparationPolicyV2(StrictModel):
    evaluation_scope: Literal["all_150_locked_manifest_cases"]
    prompt_development_source: Literal["outside_locked_corpus_only"]
    prompt_development_family_crossing: Literal["prohibited"]
    post_lock_prompt_changes: Literal["prohibited"]
    hidden_oracle_in_model_input: Literal["prohibited"]
    human_evidence_policy: Literal["optional_extension_never_required_for_any_autonomous_claim"]


class DownstreamUtilityGuardrailV2(StrictModel):
    status: Literal["required_before_full_usefulness_claim"]
    independence: Literal["benchmark_native_evaluator_not_casepath_oracle"]
    intrinsic_chain_metrics_sufficient_for_usefulness_claim: Literal[False]
    required_native_signals: tuple[
        Literal["terminal_task_success", "action_cost_or_efficiency"], ...
    ]
    terminal_success_authority: Literal["tau2_task_reward_basis"]
    process_reconstruction_authority: Literal["released_code_worfeval"]
    action_cost_definition: Literal[
        "matched_budget_model_calls_tokens_tool_calls_and_environment_steps"
    ]
    required_acceptance_benchmarks: tuple[
        Literal["worfbench-iclr2025-test", "tau2-bench-v1.0.1-core"], ...
    ]

    @model_validator(mode="after")
    def validate_guardrail(self) -> DownstreamUtilityGuardrailV2:
        if (
            set(self.required_native_signals)
            != {
                "terminal_task_success",
                "action_cost_or_efficiency",
            }
            or len(self.required_native_signals) != 2
        ):
            raise ValueError("utility guardrail requires terminal success and action cost")
        if (
            set(self.required_acceptance_benchmarks)
            != {
                "worfbench-iclr2025-test",
                "tau2-bench-v1.0.1-core",
            }
            or len(self.required_acceptance_benchmarks) != 2
        ):
            raise ValueError("utility acceptance must bind WorFBench and tau2 core")
        return self


class CustomAbsoluteFloorSpecV2(StrictModel):
    endpoint_id: EndpointV2
    direction: Literal["higher", "lower"]
    threshold: float = Field(ge=0.0, le=1.0)


class PublicCostCeilingV2(StrictModel):
    mean_model_calls_per_case: float = Field(ge=0.0)
    mean_total_tokens_per_case: float = Field(ge=0.0)
    mean_tool_calls_per_case: float = Field(ge=0.0)
    mean_environment_steps_per_case: float = Field(ge=0.0)


class PublicAbsoluteGateSpecV2(StrictModel):
    benchmark_id: Literal["worfbench-iclr2025-test", "tau2-bench-v1.0.1-core"]
    native_endpoint_id: Literal["released_code_worfeval", "tau2_task_reward_basis"]
    status: Literal["pending_audited_baseline_extraction", "pinned"]
    minimum_native_score: float | None = Field(default=None, ge=0.0, le=1.0)
    cost_ceiling: PublicCostCeilingV2 | None = None
    baseline_extraction_receipt_sha256: Sha256 | None = None

    @model_validator(mode="after")
    def validate_resolution(self) -> PublicAbsoluteGateSpecV2:
        expected_endpoint = {
            "worfbench-iclr2025-test": "released_code_worfeval",
            "tau2-bench-v1.0.1-core": "tau2_task_reward_basis",
        }[self.benchmark_id]
        if self.native_endpoint_id != expected_endpoint:
            raise ValueError("public absolute gate uses the wrong benchmark-native endpoint")
        supplied = (
            self.minimum_native_score,
            self.cost_ceiling,
            self.baseline_extraction_receipt_sha256,
        )
        resolved = all(item is not None for item in supplied)
        if self.status == "pinned" and not resolved:
            raise ValueError("a pinned public gate requires its floor, ceilings, and evidence")
        if self.status == "pending_audited_baseline_extraction" and any(
            item is not None for item in supplied
        ):
            raise ValueError("a pending public gate cannot contain unaudited thresholds")
        return self


class Tau2PublishedBaselineSourceV2(StrictModel):
    domain: Literal["airline", "retail", "telecom"]
    relative_path: str = Field(min_length=1)
    file_sha256: Sha256
    trial_count: int = Field(gt=0)
    reward_sum: float = Field(ge=0.0)
    agent_model_call_count: int = Field(ge=0)
    agent_total_tokens: int = Field(ge=0)
    agent_tool_call_count: int = Field(ge=0)
    environment_step_count: int = Field(ge=0)


class PublicFloorEvidenceReceiptV2(StrictModel):
    receipt_version: Literal["casepath.public-floor-evidence/2.1.0"]
    worf_relative_path: Literal["assets/main_results.jpg"]
    worf_source_file_sha256: Literal[
        "774feba08afb66a4af7833db71fd0a40c73f9f333246138d1ae65052ec88155b"
    ]
    worf_extraction_method: Literal["manual_table_transcription_from_pinned_image"]
    worf_best_open_average_graph_f1_percent: float = Field(ge=0.0, le=100.0)
    worf_best_closed_average_graph_f1_percent: float = Field(ge=0.0, le=100.0)
    worf_floor_formula: Literal["floor(best_open_average_graph_f1_percent)/100"]
    worf_minimum_native_score: float = Field(ge=0.0, le=1.0)
    tau2_sources: tuple[Tau2PublishedBaselineSourceV2, ...] = Field(min_length=3, max_length=3)
    tau2_aggregation_formula: Literal[
        "sum(reward)/sum(trials); costs=sum(agent-side quantity)/sum(trials)"
    ]
    tau2_trial_count: Literal[1112]
    tau2_reward_sum: Literal[684]
    tau2_agent_model_call_count: Literal[17029]
    tau2_agent_total_tokens: Literal[153306046]
    tau2_agent_tool_call_count: Literal[8390]
    tau2_environment_step_count: Literal[14010]
    tau2_published_reward: float = Field(ge=0.0, le=1.0)
    tau2_minimum_native_score: float = Field(ge=0.0, le=1.0)
    worf_cost_ceiling: PublicCostCeilingV2
    tau2_cost_ceiling: PublicCostCeilingV2
    receipt_sha256: Sha256

    @model_validator(mode="after")
    def validate_evidence(self) -> PublicFloorEvidenceReceiptV2:
        if (
            self.worf_best_open_average_graph_f1_percent != 50.46
            or self.worf_best_closed_average_graph_f1_percent != 52.53
            or self.worf_minimum_native_score != 0.5
            or self.tau2_minimum_native_score != 0.6
        ):
            raise ValueError("public native-score floors differ from the pinned evidence")
        expected_sources = {
            "airline": (
                "data/tau2/results/final/claude-3-7-sonnet-20250219_airline_default_"
                "gpt-4.1-2025-04-14_4trials.json",
                "40a2c6a246eab27db5cdefda895fbe7f44be78a23d300817248534aa606d66de",
                200,
                100.0,
                2700,
                21803786,
                1678,
                1678,
            ),
            "retail": (
                "data/tau2/results/final/claude-3-7-sonnet-20250219_retail_default_"
                "gpt-4.1-2025-04-14_4trials.json",
                "ed41dbd18c080154156484e3a0122c095e324a11367a640d88e15956daed7b9d",
                456,
                359.0,
                6287,
                47770948,
                3591,
                3591,
            ),
            "telecom": (
                "data/tau2/results/final/claude-3-7-sonnet-20250219_telecom_default_"
                "gpt-4.1-2025-04-14_4trials.json",
                "f49e540896fe91ab8631647f02eb777ef6fed5a6ebec545f43e71d0504e227b2",
                456,
                225.0,
                8042,
                83731312,
                3121,
                8741,
            ),
        }
        observed_sources = {
            item.domain: (
                item.relative_path,
                item.file_sha256,
                item.trial_count,
                item.reward_sum,
                item.agent_model_call_count,
                item.agent_total_tokens,
                item.agent_tool_call_count,
                item.environment_step_count,
            )
            for item in self.tau2_sources
        }
        if observed_sources != expected_sources or len(self.tau2_sources) != 3:
            raise ValueError("tau2 floor evidence differs from the three pinned source files")
        if abs(self.tau2_published_reward - 684 / 1112) > 1e-15:
            raise ValueError("tau2 published reward does not equal 684/1112")
        if self.worf_cost_ceiling != PublicCostCeilingV2(
            mean_model_calls_per_case=2,
            mean_total_tokens_per_case=18000,
            mean_tool_calls_per_case=0,
            mean_environment_steps_per_case=0,
        ):
            raise ValueError("WorFBench ceiling differs from the frozen static budget")
        if self.tau2_cost_ceiling != PublicCostCeilingV2(
            mean_model_calls_per_case=20,
            mean_total_tokens_per_case=150000,
            mean_tool_calls_per_case=10,
            mean_environment_steps_per_case=15,
        ):
            raise ValueError("tau2 ceiling differs from the rounded published baseline envelope")
        if self.receipt_sha256 != digest_json(
            self.model_dump(mode="json", exclude={"receipt_sha256"})
        ):
            raise ValueError("public-floor evidence receipt hash is stale")
        return self


class AbsoluteUsefulnessPolicyV2(StrictModel):
    mechanism_claim_rule: Literal["all_four_relative_headline_hypotheses_pass"]
    custom_usefulness_rule: Literal[
        "mechanism_claim_and_all_b7_pooled_and_per_domain_absolute_floors_pass"
    ]
    full_usefulness_rule: Literal[
        "custom_usefulness_and_all_public_native_floors_and_cost_ceilings_pass"
    ]
    custom_condition: Literal["B7"]
    custom_scope: Literal["pooled_and_each_domain"]
    custom_confidence_rule: Literal["two_sided_95_interval_bound"]
    custom_multiplicity_rule: Literal["intersection_union_no_adjustment"]
    custom_threshold_rationale: Literal[
        "at_least_four_in_five_required_or_valid_items_and_at_most_one_in_five_unnecessary_documents"
    ]
    custom_floors: tuple[CustomAbsoluteFloorSpecV2, ...] = Field(min_length=5, max_length=5)
    public_floor_derivation: Literal["audited_published_baseline_or_stronger_predeclared_floor"]
    unresolved_public_gate_policy: Literal["full_usefulness_claim_fails_closed"]
    public_gates: tuple[PublicAbsoluteGateSpecV2, ...] = Field(min_length=2, max_length=2)

    @model_validator(mode="after")
    def validate_policy(self) -> AbsoluteUsefulnessPolicyV2:
        expected_custom = {
            "critical_evidence_recall": ("higher", 0.8),
            "unnecessary_document_rate": ("lower", 0.2),
            "valid_chain_precision": ("higher", 0.8),
            "fact_chain_completeness": ("higher", 0.8),
            "evidence_obligation_completeness": ("higher", 0.8),
        }
        observed_custom = {
            item.endpoint_id: (item.direction, item.threshold) for item in self.custom_floors
        }
        if observed_custom != expected_custom or len(self.custom_floors) != 5:
            raise ValueError("custom usefulness requires the five frozen 80/20 task floors")
        if {item.benchmark_id for item in self.public_gates} != {
            "worfbench-iclr2025-test",
            "tau2-bench-v1.0.1-core",
        } or len(self.public_gates) != 2:
            raise ValueError("public usefulness gates must cover WorFBench and tau2 core")
        public = {item.benchmark_id: item for item in self.public_gates}
        evidence_sha256 = "80a82bb3a0ee2523de67ae21d96718f519b6384cd86f3464473aba4b309d8fa4"
        expected_public: dict[
            Literal["worfbench-iclr2025-test", "tau2-bench-v1.0.1-core"],
            tuple[float, PublicCostCeilingV2],
        ] = {
            "worfbench-iclr2025-test": (
                0.5,
                PublicCostCeilingV2(
                    mean_model_calls_per_case=2,
                    mean_total_tokens_per_case=18000,
                    mean_tool_calls_per_case=0,
                    mean_environment_steps_per_case=0,
                ),
            ),
            "tau2-bench-v1.0.1-core": (
                0.6,
                PublicCostCeilingV2(
                    mean_model_calls_per_case=20,
                    mean_total_tokens_per_case=150000,
                    mean_tool_calls_per_case=10,
                    mean_environment_steps_per_case=15,
                ),
            ),
        }
        if any(
            public[benchmark_id].status != "pinned"
            or public[benchmark_id].minimum_native_score != floor
            or public[benchmark_id].cost_ceiling != ceiling
            or public[benchmark_id].baseline_extraction_receipt_sha256 != evidence_sha256
            for benchmark_id, (floor, ceiling) in expected_public.items()
        ):
            raise ValueError("public floors and cost ceilings differ from the pinned evidence")
        return self


class PublicationProtocolV2(StrictModel):
    protocol_version: Literal["casepath.publication-protocol/2.1.0"]
    protocol_id: Literal["casepath-publication-v2.1"]
    relationship_to_v1: Literal["new_study_v1_unchanged"]
    status: Literal["specified_not_yet_locked"]
    research_claim: Literal[
        "B7 improves critical-evidence recall over B3 and B6 while preserving "
        "unnecessary-document rate"
    ]
    corpus: LockedCorpusIdentityV2
    conditions: tuple[ConditionV2, ...] = Field(min_length=5, max_length=5)
    endpoints: tuple[AutonomousEndpointSpecV2, ...] = Field(min_length=5, max_length=5)
    estimand: GroupAwareEstimandV2
    multiplicity_families: tuple[MultiplicityFamilyV2, ...] = Field(min_length=4, max_length=4)
    headline_operator: Literal["all_four_custom_headline_hypotheses_must_pass"]
    separation: SeparationPolicyV2
    downstream_utility_guardrail: DownstreamUtilityGuardrailV2
    absolute_usefulness: AbsoluteUsefulnessPolicyV2
    required_study_lock_receipts: tuple[
        Literal[
            "compiler",
            "oracle_audit",
            "leakage_audit",
            "public_benchmark_suite",
            "statistical_simulation",
            "model_input_bundle",
            "public_floor_evidence",
        ],
        ...,
    ]

    @model_validator(mode="after")
    def validate_protocol(self) -> PublicationProtocolV2:
        if self.conditions != ("B3", "B6", "B7", "B8", "B9"):
            raise ValueError("publication v2 condition order must be B3/B6/B7/B8/B9")
        endpoint_map = {endpoint.endpoint_id: endpoint for endpoint in self.endpoints}
        if len(endpoint_map) != 5:
            raise ValueError("publication v2 requires five unique autonomous endpoints")
        expected_directions = {
            "critical_evidence_recall": "higher",
            "unnecessary_document_rate": "lower",
            "valid_chain_precision": "higher",
            "fact_chain_completeness": "higher",
            "evidence_obligation_completeness": "higher",
        }
        if {key: value.direction for key, value in endpoint_map.items()} != expected_directions:
            raise ValueError("publication endpoint set or benefit direction differs")

        families = {family.family_id: family for family in self.multiplicity_families}
        if len(families) != 4:
            raise ValueError("publication v2 requires four separate multiplicity families")
        headline = families.get("custom_headline")
        if headline is None or headline.role != "headline" or not headline.required_for_headline:
            raise ValueError("only the custom headline family may control headline success")
        if any(
            family.required_for_headline
            for family_id, family in families.items()
            if family_id != "custom_headline"
        ):
            raise ValueError("secondary and falsification families cannot control the headline")
        if headline.familywise_alpha != 0.04 or any(
            family.familywise_alpha != 0.05
            for family_id, family in families.items()
            if family_id != "custom_headline"
        ):
            raise ValueError("headline Holm alpha must be 0.04; other families use 0.05")

        expected_headline = {
            ("B7", "B3", "critical_evidence_recall", "superiority", 0.03),
            ("B7", "B6", "critical_evidence_recall", "superiority", 0.03),
            ("B7", "B3", "unnecessary_document_rate", "noninferiority", 0.03),
            ("B7", "B6", "unnecessary_document_rate", "noninferiority", 0.03),
        }
        observed_headline = {
            (
                item.treatment,
                item.control,
                item.endpoint_id,
                item.decision_rule,
                item.margin,
            )
            for item in headline.hypotheses
        }
        if observed_headline != expected_headline or len(headline.hypotheses) != 4:
            raise ValueError(
                "headline must contain only the two recall and two document-rate tests"
            )

        mechanism = families.get("mechanism_secondary")
        if mechanism is None or mechanism.role != "secondary_mechanism":
            raise ValueError("mechanistic chain metrics require their own secondary family")
        expected_mechanism = {
            (control, endpoint)
            for control in ("B3", "B6")
            for endpoint in (
                "valid_chain_precision",
                "fact_chain_completeness",
                "evidence_obligation_completeness",
            )
        }
        if {
            (item.control, item.endpoint_id) for item in mechanism.hypotheses
        } != expected_mechanism or any(
            item.treatment != "B7" or item.decision_rule != "superiority" or item.margin != 0.03
            for item in mechanism.hypotheses
        ):
            raise ValueError("mechanistic family must be B7 superiority over B3 and B6")

        b8 = families.get("b8_verifier_falsification")
        b9 = families.get("b9_novelty_falsification")
        if b8 is None or b9 is None or b8.role != "falsification" or b9.role != "falsification":
            raise ValueError("B8 and B9 must remain separate falsification families")
        if any(item.treatment != "B8" or item.control != "B7" for item in b8.hypotheses):
            raise ValueError("B8 falsification must compare the derived verifier with B7")
        if any(item.treatment != "B7" or item.control != "B9" for item in b9.hypotheses):
            raise ValueError("B9 falsification must compare B7 with the adapted external baseline")

        hypothesis_ids = [
            item.hypothesis_id
            for family in self.multiplicity_families
            for item in family.hypotheses
        ]
        if len(hypothesis_ids) != len(set(hypothesis_ids)):
            raise ValueError("hypothesis IDs must be globally unique")
        if (
            set(self.required_study_lock_receipts)
            != {
                "compiler",
                "oracle_audit",
                "leakage_audit",
                "public_benchmark_suite",
                "statistical_simulation",
                "model_input_bundle",
                "public_floor_evidence",
            }
            or len(self.required_study_lock_receipts) != 7
        ):
            raise ValueError("study lock must bind all seven required receipt kinds")
        return self


class CompilerReceiptV2(StrictModel):
    receipt_version: Literal["casepath.publication-compiler-receipt/2.0.0"]
    compiler_version: str = Field(min_length=1)
    compiler_code_sha256: Sha256
    source_manifest_file_sha256: Sha256
    source_corpus_sha256: Sha256
    cohort_sha256: Sha256
    compiled_case_count: Literal[150]
    model_packet_file_set_sha256: Sha256
    oracle_file_set_sha256: Sha256
    runtime_model_calls: Literal[0]
    receipt_sha256: Sha256

    @model_validator(mode="after")
    def validate_receipt_hash(self) -> CompilerReceiptV2:
        if self.receipt_sha256 != digest_json(
            self.model_dump(mode="json", exclude={"receipt_sha256"})
        ):
            raise ValueError("compiler receipt hash is stale")
        return self


class OracleAuditReceiptV2(StrictModel):
    receipt_version: Literal["casepath.oracle-audit-receipt/2.0.0"]
    audit_method: Literal["independent_executable_invariant_replay"]
    compiler_receipt_sha256: Sha256
    audited_case_count: Literal[150]
    audited_family_count: Literal[28]
    acceptance_contracts_valid: Literal[150]
    branch_truth_tables_valid: Literal[150]
    document_oracles_valid: Literal[150]
    failures: tuple[str, ...] = ()
    evidence_bundle_sha256: Sha256
    audit_code_sha256: Sha256
    receipt_sha256: Sha256

    @model_validator(mode="after")
    def validate_audit(self) -> OracleAuditReceiptV2:
        if self.failures:
            raise ValueError("a study lock cannot bind an oracle audit with failures")
        if self.receipt_sha256 != digest_json(
            self.model_dump(mode="json", exclude={"receipt_sha256"})
        ):
            raise ValueError("oracle-audit receipt hash is stale")
        return self


class LeakageAuditReceiptV2(StrictModel):
    receipt_version: Literal["casepath.leakage-audit-receipt/2.0.0"]
    cohort_sha256: Sha256
    prompt_template_sha256: Sha256
    model_input_bundle_sha256: Sha256
    adapter_sha256: Sha256
    evaluation_family_ids: tuple[str, ...] = Field(min_length=28, max_length=28)
    prompt_development_family_ids: tuple[str, ...] = ()
    forbidden_gold_fields_scanned: tuple[str, ...] = Field(min_length=1)
    forbidden_gold_matches: Literal[0]
    prompt_eval_family_overlap_count: Literal[0]
    observable_oracle_identifier_overlap_count: Literal[0]
    evidence_bundle_sha256: Sha256
    audit_code_sha256: Sha256
    receipt_sha256: Sha256

    @model_validator(mode="after")
    def validate_audit(self) -> LeakageAuditReceiptV2:
        if len(set(self.evaluation_family_ids)) != 28:
            raise ValueError("leakage audit must cover 28 unique evaluation families")
        if set(self.evaluation_family_ids).intersection(self.prompt_development_family_ids):
            raise ValueError("prompt-development and evaluation families overlap")
        if self.receipt_sha256 != digest_json(
            self.model_dump(mode="json", exclude={"receipt_sha256"})
        ):
            raise ValueError("leakage-audit receipt hash is stale")
        return self


class ModelInputBundleReceiptV2(StrictModel):
    """Content identity for every byte and rule visible to the model."""

    receipt_version: Literal["casepath.model-input-bundle-receipt/2.1.0"]
    prompt_template_sha256: Sha256
    projection_contract: Literal["casepath.text-model-projection/1.0.0"]
    projection_identity: str = Field(min_length=1)
    closed_vocabulary_ontology_contract: Literal["casepath.closed-vocabulary-ontology/1.0.0"]
    closed_vocabulary_ontology_sha256: Sha256
    projected_input_file_set_sha256: Sha256
    projected_case_count: Literal[150]
    forbidden_evaluator_field_count: Literal[0]
    bundle_sha256: Sha256

    @model_validator(mode="after")
    def validate_bundle_hash(self) -> ModelInputBundleReceiptV2:
        if self.bundle_sha256 != digest_json(
            self.model_dump(mode="json", exclude={"bundle_sha256"})
        ):
            raise ValueError("model-input bundle hash is stale")
        return self


class PublicBenchmarkCandidateV2(StrictModel):
    benchmark_id: Literal[
        "paged-acl2024-test",
        "worfbench-iclr2025-test",
        "tau2-bench-v1.0.1-core",
        "tau2-bench-v1.0.1-banking-knowledge",
    ]
    display_name: str = Field(min_length=1)
    overlap_claim: str = Field(min_length=1)
    code_revision: str = Field(pattern=r"^[0-9a-f]{40}$")
    native_evaluator: str = Field(min_length=1)
    audit_status: Literal["audit_pending"]
    metric_semantics_note: str = Field(min_length=1)


class PublicBenchmarkSuiteReceiptV2(StrictModel):
    receipt_version: Literal["casepath.public-benchmark-suite/2.0.0"]
    status: Literal["declarative_audit_pending"]
    candidates: tuple[PublicBenchmarkCandidateV2, ...] = Field(min_length=3)
    score_admission_policy: Literal[
        "no_score_without_native_evaluator_and_complete_provenance_audit"
    ]
    receipt_sha256: Sha256

    @model_validator(mode="after")
    def validate_suite(self) -> PublicBenchmarkSuiteReceiptV2:
        benchmark_ids = [candidate.benchmark_id for candidate in self.candidates]
        if len(benchmark_ids) != len(set(benchmark_ids)):
            raise ValueError("public benchmark candidate IDs must be unique")
        if self.receipt_sha256 != digest_json(
            self.model_dump(mode="json", exclude={"receipt_sha256"})
        ):
            raise ValueError("public benchmark suite receipt hash is stale")
        return self


class PublicBenchmarkAuditReceiptV2(StrictModel):
    receipt_version: Literal["casepath.public-benchmark-audit/2.0.0"]
    benchmark_id: str = Field(min_length=1)
    approved_for_run: Literal[True]
    provenance_manifest_sha256: Sha256
    code_revision: str = Field(pattern=r"^[0-9a-f]{40}$")
    native_evaluator: str = Field(min_length=1)
    native_evaluator_sha256: Sha256
    split_id: str = Field(min_length=1)
    split_sha256: Sha256
    data_sha256: Sha256
    license_sha256: Sha256
    adapter_sha256: Sha256
    forbidden_gold_fields: tuple[str, ...]
    forbidden_gold_matches: Literal[0]
    expected_native_case_count: int = Field(gt=0)
    expected_trials_per_case: int = Field(gt=0)
    audit_code_sha256: Sha256
    receipt_sha256: Sha256

    @model_validator(mode="after")
    def validate_audit_hash(self) -> PublicBenchmarkAuditReceiptV2:
        if self.receipt_sha256 != digest_json(
            self.model_dump(mode="json", exclude={"receipt_sha256"})
        ):
            raise ValueError("public benchmark audit receipt hash is stale")
        return self


class PublicBenchmarkRunManifestV2(StrictModel):
    manifest_version: Literal["casepath.public-benchmark-run/2.0.0"]
    benchmark_id: str = Field(min_length=1)
    audit_receipt_sha256: Sha256
    provenance_manifest_sha256: Sha256
    code_revision: str = Field(pattern=r"^[0-9a-f]{40}$")
    native_evaluator: str = Field(min_length=1)
    native_evaluator_sha256: Sha256
    split_id: str = Field(min_length=1)
    split_sha256: Sha256
    data_sha256: Sha256
    license_sha256: Sha256
    adapter_sha256: Sha256
    prompt_template_sha256: Sha256
    model_input_bundle_sha256: Sha256
    model_revision_sha256: Sha256
    budget_spec_sha256: Sha256
    native_case_count: int = Field(gt=0)
    trials_per_case: int = Field(gt=0)
    native_endpoint_ids: tuple[str, ...] = Field(min_length=1)
    action_cost_receipt_sha256: Sha256
    complete_native_outputs_sha256: Sha256
    native_score_receipt_sha256: Sha256


class PublicAbsoluteGateResultV2(StrictModel):
    benchmark_id: Literal["worfbench-iclr2025-test", "tau2-bench-v1.0.1-core"]
    native_endpoint_id: Literal["released_code_worfeval", "tau2_task_reward_basis"]
    native_score: float = Field(ge=0.0, le=1.0)
    minimum_native_score: float = Field(ge=0.0, le=1.0)
    observed_cost: PublicCostCeilingV2
    cost_ceiling: PublicCostCeilingV2
    native_floor_passed: bool
    cost_ceiling_passed: bool
    passed: bool

    @model_validator(mode="after")
    def validate_decision(self) -> PublicAbsoluteGateResultV2:
        expected_endpoint = {
            "worfbench-iclr2025-test": "released_code_worfeval",
            "tau2-bench-v1.0.1-core": "tau2_task_reward_basis",
        }[self.benchmark_id]
        if self.native_endpoint_id != expected_endpoint:
            raise ValueError("public result uses the wrong benchmark-native endpoint")
        score_pass = self.native_score >= self.minimum_native_score
        cost_pass = all(
            getattr(self.observed_cost, field) <= getattr(self.cost_ceiling, field)
            for field in PublicCostCeilingV2.model_fields
        )
        if self.native_floor_passed != score_pass:
            raise ValueError("public native-score floor decision is stale")
        if self.cost_ceiling_passed != cost_pass:
            raise ValueError("public cost-ceiling decision is stale")
        if self.passed != (score_pass and cost_pass):
            raise ValueError("public absolute-gate decision is stale")
        return self


class PublicSuiteAcceptanceReceiptV2(StrictModel):
    receipt_version: Literal["casepath.public-suite-acceptance/2.1.0"]
    protocol_sha256: Sha256
    suite_receipt_sha256: Sha256
    absolute_gate_spec_sha256: Sha256
    public_floor_evidence_receipt_sha256: Sha256
    worfbench_run_manifest_sha256: Sha256
    tau2_core_run_manifest_sha256: Sha256
    worfbench_paired_acceptance_receipt_sha256: Sha256
    tau2_core_paired_acceptance_receipt_sha256: Sha256
    process_reconstruction_endpoint: Literal["released_code_worfeval"]
    terminal_task_success_endpoint: Literal["tau2_task_reward_basis"]
    action_cost_endpoint: Literal[
        "matched_budget_model_calls_tokens_tool_calls_and_environment_steps"
    ]
    absolute_gate_results: tuple[PublicAbsoluteGateResultV2, ...] = Field(
        min_length=2, max_length=2
    )
    absolute_public_gates_passed: bool
    matched_arm_noninferiority_superiority_passed: Literal[True]
    full_usefulness_public_guardrail_passed: bool
    all_native_cases_and_trials_present: Literal[True]
    human_evidence_used: Literal[False]
    receipt_sha256: Sha256

    @model_validator(mode="after")
    def validate_receipt(self) -> PublicSuiteAcceptanceReceiptV2:
        if {item.benchmark_id for item in self.absolute_gate_results} != {
            "worfbench-iclr2025-test",
            "tau2-bench-v1.0.1-core",
        } or len(self.absolute_gate_results) != 2:
            raise ValueError("public acceptance requires one absolute result per benchmark")
        expected_pass = all(item.passed for item in self.absolute_gate_results)
        if self.absolute_public_gates_passed != expected_pass:
            raise ValueError("public absolute-gate decision is stale")
        if self.full_usefulness_public_guardrail_passed != expected_pass:
            raise ValueError("public usefulness guardrail decision is stale")
        if self.receipt_sha256 != digest_json(
            self.model_dump(mode="json", exclude={"receipt_sha256"})
        ):
            raise ValueError("public-suite acceptance receipt hash is stale")
        return self


class StatisticalSimulationAcceptanceReceiptV2(StrictModel):
    receipt_version: Literal["casepath.statistical-simulation-acceptance/2.1.0"]
    protocol_sha256: Sha256
    simulation_code_sha256: Sha256
    independent_reference_code_sha256: Sha256
    report_sha256: Sha256
    exact_case_count: Literal[150]
    exact_family_count: Literal[28]
    exact_domain_family_counts: dict[DomainV2, int]
    null_replications_per_icc: int = Field(ge=10000)
    maximum_headline_fwer: float = Field(ge=0.0, le=0.05)
    maximum_headline_fwer_wilson_upper_95: float = Field(ge=0.0, le=0.05)
    minimum_interval_coverage: float = Field(ge=0.93, le=0.97)
    maximum_interval_coverage: float = Field(ge=0.93, le=0.97)
    maximum_point_crosscheck_error: float = Field(ge=0.0, le=1e-12)
    maximum_interval_crosscheck_error: float = Field(ge=0.0, le=1e-10)
    missing_casepath_effect_delta: float = Field(le=0.0)
    power_mde_table_sha256: Sha256
    accepted: Literal[True]
    receipt_sha256: Sha256

    @model_validator(mode="after")
    def validate_acceptance(self) -> StatisticalSimulationAcceptanceReceiptV2:
        if self.exact_domain_family_counts != {
            "defect_mold_heating": 10,
            "lease_termination_dispute": 8,
            "rent_increase_dispute": 10,
        }:
            raise ValueError("simulation receipt does not cover the exact 10/8/10 design")
        if self.minimum_interval_coverage > self.maximum_interval_coverage:
            raise ValueError("simulation coverage bounds are reversed")
        if self.receipt_sha256 != digest_json(
            self.model_dump(mode="json", exclude={"receipt_sha256"})
        ):
            raise ValueError("statistical-simulation receipt hash is stale")
        return self


class PublicationStudyLockV2(StrictModel):
    receipt_version: Literal["casepath.publication-study-lock/2.1.0"]
    study_id: Literal["casepath-publication-v2.1"]
    locked_at: datetime
    protocol_sha256: Sha256
    cohort_sha256: Sha256
    source_manifest_file_sha256: Sha256
    source_corpus_sha256: Sha256
    analysis_code_sha256: Sha256
    absolute_usefulness_policy_sha256: Sha256
    prompt_template_sha256: Sha256
    model_input_bundle_sha256: Sha256
    autonomous_runtime_schedule_sha256: Sha256
    evaluator_bundle_sha256: Sha256
    model_revision_sha256: Sha256
    budget_spec_sha256: Sha256
    runtime_image_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    compiler_receipt_sha256: Sha256
    oracle_audit_receipt_sha256: Sha256
    leakage_audit_receipt_sha256: Sha256
    public_benchmark_suite_receipt_sha256: Sha256
    statistical_simulation_receipt_sha256: Sha256
    public_floor_evidence_receipt_sha256: Sha256
    optional_human_extension_sha256: Sha256 | None = None
    human_evidence_required: Literal[False]
    all_150_custom_cases_required: Literal[True]
    post_lock_mutation_policy: Literal["new_protocol_version_required"]

    @model_validator(mode="after")
    def validate_timestamp(self) -> PublicationStudyLockV2:
        if self.locked_at.tzinfo is None:
            raise ValueError("publication study lock timestamp must include a timezone")
        return self


OutcomeStatusV2 = Literal["observed", "missing", "system_failure"]


class AutonomousOutcomeV2(StrictModel):
    case_id: str = Field(min_length=1)
    condition: ConditionV2
    endpoint_id: EndpointV2
    status: OutcomeStatusV2
    value: float | None = None

    @model_validator(mode="after")
    def validate_value(self) -> AutonomousOutcomeV2:
        if (self.status == "observed") != (self.value is not None):
            raise ValueError("only observed autonomous outcomes may contain a value")
        if self.value is not None and not 0.0 <= self.value <= 1.0:
            raise ValueError("autonomous endpoint values must lie in [0, 1]")
        return self


class AutonomousOutcomeBundleV2(StrictModel):
    bundle_version: Literal["casepath.autonomous-outcomes/2.0.0"]
    study_lock_sha256: Sha256
    cohort_sha256: Sha256
    outcomes: tuple[AutonomousOutcomeV2, ...] = Field(min_length=1)


class PublicationEstimateV2(StrictModel):
    hypothesis_id: str
    family_id: str
    endpoint_id: EndpointV2
    treatment: ConditionV2
    control: ConditionV2
    decision_rule: DecisionRuleV2
    margin: float
    benefit_estimate: float
    confidence_lower: float
    confidence_upper: float
    raw_p_value: float = Field(ge=0.0, le=1.0)
    adjusted_p_value: float = Field(ge=0.0, le=1.0)
    margin_passed: bool
    multiplicity_passed: bool
    passed: bool
    analyzed_cases: Literal[150]
    analyzed_families: Literal[28]
    analyzed_domains: Literal[3]
    treatment_missing: int = Field(ge=0)
    control_missing: int = Field(ge=0)
    treatment_failures: int = Field(ge=0)
    control_failures: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_interval(self) -> PublicationEstimateV2:
        if not self.confidence_lower <= self.benefit_estimate <= self.confidence_upper:
            raise ValueError("estimate must lie inside its cluster-t confidence interval")
        if self.passed != (self.margin_passed and self.multiplicity_passed):
            raise ValueError("hypothesis pass must join margin and multiplicity decisions")
        return self


AbsoluteFloorScopeV2 = Literal[
    "pooled",
    "defect_mold_heating",
    "lease_termination_dispute",
    "rent_increase_dispute",
]


class CustomAbsoluteFloorResultV2(StrictModel):
    condition: Literal["B7"]
    endpoint_id: EndpointV2
    scope: AbsoluteFloorScopeV2
    direction: Literal["higher", "lower"]
    threshold: float = Field(ge=0.0, le=1.0)
    estimate: float = Field(ge=0.0, le=1.0)
    confidence_lower: float
    confidence_upper: float
    passed: bool
    analyzed_cases: int = Field(ge=1, le=150)
    analyzed_families: int = Field(ge=2, le=28)
    analyzed_domains: int = Field(ge=1, le=3)

    @model_validator(mode="after")
    def validate_decision(self) -> CustomAbsoluteFloorResultV2:
        if not self.confidence_lower <= self.estimate <= self.confidence_upper:
            raise ValueError("absolute estimate must lie inside its cluster-t interval")
        expected = (
            self.confidence_lower >= self.threshold
            if self.direction == "higher"
            else self.confidence_upper <= self.threshold
        )
        if self.passed != expected:
            raise ValueError("custom absolute-floor decision is stale")
        return self


class LanguageEstimateV2(StrictModel):
    hypothesis_id: str
    language: LanguageV2
    benefit_estimate: float
    confidence_lower: float
    confidence_upper: float
    analyzed_cases: Literal[75]
    analyzed_families: int = Field(ge=2, le=28)
    analyzed_domains: Literal[3]

    @model_validator(mode="after")
    def validate_interval(self) -> LanguageEstimateV2:
        if not self.confidence_lower <= self.benefit_estimate <= self.confidence_upper:
            raise ValueError("language estimate must lie inside its cluster-t interval")
        return self


class DeletionEstimateV2(StrictModel):
    excluded_id: str = Field(min_length=1)
    benefit_estimate: float


class SensitivitySummaryV2(StrictModel):
    hypothesis_id: str
    full_benefit_estimate: float
    leave_one_family: tuple[DeletionEstimateV2, ...] = Field(min_length=28, max_length=28)
    leave_one_domain: tuple[DeletionEstimateV2, ...] = Field(min_length=3, max_length=3)
    maximum_absolute_family_shift: float = Field(ge=0.0)
    maximum_absolute_domain_shift: float = Field(ge=0.0)

    @model_validator(mode="after")
    def validate_deletions(self) -> SensitivitySummaryV2:
        family_ids = [item.excluded_id for item in self.leave_one_family]
        domain_ids = [item.excluded_id for item in self.leave_one_domain]
        if len(set(family_ids)) != 28 or len(set(domain_ids)) != 3:
            raise ValueError("sensitivity deletions must cover 28 families and three domains")
        family_shift = max(
            abs(item.benefit_estimate - self.full_benefit_estimate)
            for item in self.leave_one_family
        )
        domain_shift = max(
            abs(item.benefit_estimate - self.full_benefit_estimate)
            for item in self.leave_one_domain
        )
        if abs(self.maximum_absolute_family_shift - family_shift) > 1e-12:
            raise ValueError("maximum family sensitivity shift is stale")
        if abs(self.maximum_absolute_domain_shift - domain_shift) > 1e-12:
            raise ValueError("maximum domain sensitivity shift is stale")
        return self


class PublicationAnalysisReceiptV2(StrictModel):
    receipt_version: Literal["casepath.publication-analysis/2.1.0"]
    protocol_sha256: Sha256
    study_lock_sha256: Sha256
    cohort_sha256: Sha256
    outcome_bundle_sha256: Sha256
    estimates: tuple[PublicationEstimateV2, ...] = Field(min_length=1)
    language_secondary: tuple[LanguageEstimateV2, ...] = Field(min_length=2)
    sensitivity: tuple[SensitivitySummaryV2, ...] = Field(min_length=1)
    custom_absolute_floor_results: tuple[CustomAbsoluteFloorResultV2, ...] = Field(
        min_length=20, max_length=20
    )
    headline_hypothesis_ids: tuple[str, ...] = Field(min_length=4, max_length=4)
    relative_mechanism_claim_success: bool
    custom_absolute_quality_success: bool
    headline_success: bool
    full_usefulness_claim_status: Literal["requires_separate_public_suite_acceptance"]
    human_evidence_used: Literal[False]
    receipt_sha256: Sha256

    @model_validator(mode="after")
    def validate_receipt(self) -> PublicationAnalysisReceiptV2:
        estimate_map = {estimate.hypothesis_id: estimate for estimate in self.estimates}
        if len(estimate_map) != len(self.estimates):
            raise ValueError("analysis receipt contains duplicate hypothesis estimates")
        if set(self.headline_hypothesis_ids) - set(estimate_map):
            raise ValueError("headline references an absent estimate")
        expected_language = {
            (hypothesis_id, language)
            for hypothesis_id in estimate_map
            for language in ("de-CH", "en")
        }
        if {
            (item.hypothesis_id, item.language) for item in self.language_secondary
        } != expected_language:
            raise ValueError("language-secondary output must cover every hypothesis and language")
        if {item.hypothesis_id for item in self.sensitivity} != set(estimate_map):
            raise ValueError("sensitivity output must cover every hypothesis")
        expected_floor_keys = {
            (endpoint, scope)
            for endpoint in (
                "critical_evidence_recall",
                "unnecessary_document_rate",
                "valid_chain_precision",
                "fact_chain_completeness",
                "evidence_obligation_completeness",
            )
            for scope in (
                "pooled",
                "defect_mold_heating",
                "lease_termination_dispute",
                "rent_increase_dispute",
            )
        }
        if {
            (item.endpoint_id, item.scope) for item in self.custom_absolute_floor_results
        } != expected_floor_keys:
            raise ValueError(
                "custom absolute-floor output must cover five endpoints and four scopes"
            )
        mechanism_success = all(estimate_map[item].passed for item in self.headline_hypothesis_ids)
        floor_success = all(item.passed for item in self.custom_absolute_floor_results)
        if self.relative_mechanism_claim_success != mechanism_success:
            raise ValueError("relative mechanism decision is stale")
        if self.custom_absolute_quality_success != floor_success:
            raise ValueError("custom absolute-quality decision is stale")
        if self.headline_success != (mechanism_success and floor_success):
            raise ValueError("headline success must join relative tests and absolute floors")
        if self.receipt_sha256 != digest_json(
            self.model_dump(mode="json", exclude={"receipt_sha256"})
        ):
            raise ValueError("publication analysis receipt hash is stale")
        return self
