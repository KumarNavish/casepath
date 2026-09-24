"""Frozen confirmatory-analysis contract and decision receipts."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field, model_validator

from .schema import StrictModel

ConditionId = Literal["B3", "B6", "B7", "B8", "B9"]
EndpointDirection = Literal["higher", "lower"]
DecisionRule = Literal["superiority", "equivalence", "noninferiority"]
InferenceMethod = Literal[
    "paired_case_bca_bootstrap",
    "crossed_case_reviewer_bootstrap",
]
Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class PilotConfirmatorySeparation(StrictModel):
    pilot_role: Literal["design_only"]
    pilot_cases_excluded_from_confirmatory: Literal[True]
    confirmatory_labels_hidden_until_freeze: Literal[True]
    specification_changes_after_freeze: Literal["prohibited"]


class ContrastSpec(StrictModel):
    contrast_id: str
    role: Literal["primary", "secondary"]
    treatment: ConditionId
    control: ConditionId


class DecisionMargins(StrictModel):
    superiority: float = Field(ge=0.0)
    equivalence: float = Field(gt=0.0)
    noninferiority: float = Field(gt=0.0)


class EndpointSpec(StrictModel):
    endpoint_id: str
    source: Literal["automated", "human"]
    unit: str
    direction: EndpointDirection
    minimum: float
    maximum: float
    missing_score: float
    system_failure_score: float
    margins: DecisionMargins

    @model_validator(mode="after")
    def validate_scores(self) -> EndpointSpec:
        if self.maximum <= self.minimum:
            raise ValueError("endpoint maximum must exceed minimum")
        for name, value in (
            ("missing_score", self.missing_score),
            ("system_failure_score", self.system_failure_score),
        ):
            if not self.minimum <= value <= self.maximum:
                raise ValueError(f"{name} must fall inside the endpoint range")
        return self


class FamilyMemberSpec(StrictModel):
    endpoint_id: str
    decision_rule: DecisionRule
    inference_method: InferenceMethod


class MultiplicityFamilySpec(StrictModel):
    family_id: str
    role: Literal["primary", "secondary", "optional_external_validity"]
    required_for_confirmatory_decision: bool
    contrast_ids: tuple[str, ...] = Field(min_length=1)
    members: tuple[FamilyMemberSpec, ...] = Field(min_length=1)
    correction: Literal["holm"]
    familywise_alpha: float = Field(gt=0.0, lt=1.0)


class ReviewerClusteringSpec(StrictModel):
    enabled: Literal[True]
    availability: Literal["optional_external_validity"]
    endpoint_ids: tuple[str, ...] = Field(min_length=1)
    case_field: Literal["case_id"]
    reviewer_field: Literal["reviewer_id"]
    method: Literal["crossed_case_reviewer_bootstrap"]
    minimum_reviewers: int = Field(ge=2)


class PValueSemanticsSpec(StrictModel):
    superiority: Literal["exact_paired_sign_at_superiority_margin"]
    noninferiority: Literal["exact_paired_sign_at_negative_noninferiority_margin"]
    equivalence: Literal["maximum_exact_paired_sign_at_equivalence_bounds"]


class HeadlineSuccessSpec(StrictModel):
    operator: Literal["all"]
    required_hypothesis_ids: tuple[str, ...] = Field(min_length=1)


class NoveltyDecisionSpec(StrictModel):
    kill_operator: Literal["all"]
    kill_hypothesis_ids: tuple[str, ...] = Field(min_length=1)
    novelty_supported_when: Literal[
        "kill_not_triggered_and_b9_upper_bound_below_negative_superiority_margin"
    ]


class SampleSizeAssumptions(StrictModel):
    familywise_alpha: float = Field(gt=0.0, lt=1.0)
    primary_hypothesis_count: Literal[10]
    target_power: float = Field(gt=0.0, lt=1.0)
    target_absolute_effect: float = Field(gt=0.0)
    dropout_fraction: float = Field(ge=0.0, lt=1.0)
    domain_count: Literal[3]
    williams_sequence_count: Literal[4]

    @model_validator(mode="after")
    def validate_frozen_values(self) -> SampleSizeAssumptions:
        if (
            self.familywise_alpha,
            self.target_power,
            self.target_absolute_effect,
            self.dropout_fraction,
        ) != (0.05, 0.8, 0.1, 0.1):
            raise ValueError("sample-size assumptions differ from the frozen design")
        return self


def hypothesis_id(family_id: str, contrast_id: str, endpoint_id: str) -> str:
    return f"{family_id}:{contrast_id}:{endpoint_id}"


class ConfirmatoryAnalysisSpec(StrictModel):
    spec_version: Literal["casepath.confirmatory-analysis-spec/0.1.0"]
    spec_id: str
    status: Literal["frozen"]
    evaluation_authority: Literal["executable_hidden_state"]
    cohort_id: str
    target_case_count: int = Field(gt=0)
    resamples: Literal[10000]
    confidence_level: float = Field(gt=0.0, lt=1.0)
    random_seed: int = Field(ge=0)
    sample_size: SampleSizeAssumptions
    separation: PilotConfirmatorySeparation
    contrasts: tuple[ContrastSpec, ...]
    endpoints: tuple[EndpointSpec, ...]
    multiplicity_families: tuple[MultiplicityFamilySpec, ...]
    reviewer_clustering: ReviewerClusteringSpec
    p_value_semantics: PValueSemanticsSpec
    headline_success: HeadlineSuccessSpec
    novelty_decision: NoveltyDecisionSpec

    @property
    def hypotheses(self) -> dict[str, tuple[ContrastSpec, EndpointSpec, FamilyMemberSpec]]:
        contrasts = {contrast.contrast_id: contrast for contrast in self.contrasts}
        endpoints = {endpoint.endpoint_id: endpoint for endpoint in self.endpoints}
        return {
            hypothesis_id(family.family_id, contrast_id, member.endpoint_id): (
                contrasts[contrast_id],
                endpoints[member.endpoint_id],
                member,
            )
            for family in self.multiplicity_families
            for contrast_id in family.contrast_ids
            for member in family.members
        }

    @model_validator(mode="after")
    def validate_frozen_design(self) -> ConfirmatoryAnalysisSpec:
        if self.confidence_level != 0.95:
            raise ValueError("confidence_level must be 0.95")
        if self.target_case_count % 4:
            raise ValueError("target_case_count must contain complete four-sequence blocks")

        contrast_ids = [contrast.contrast_id for contrast in self.contrasts]
        endpoint_ids = [endpoint.endpoint_id for endpoint in self.endpoints]
        family_ids = [family.family_id for family in self.multiplicity_families]
        if len(contrast_ids) != len(set(contrast_ids)):
            raise ValueError("contrast IDs must be unique")
        if len(endpoint_ids) != len(set(endpoint_ids)):
            raise ValueError("endpoint IDs must be unique")
        if len(family_ids) != len(set(family_ids)):
            raise ValueError("multiplicity-family IDs must be unique")

        expected_contrasts = {
            ("b7_minus_b3", "primary", "B7", "B3"),
            ("b7_minus_b6", "primary", "B7", "B6"),
            ("b8_minus_b7", "secondary", "B8", "B7"),
            ("b9_minus_b7", "secondary", "B9", "B7"),
        }
        observed_contrasts = {
            (item.contrast_id, item.role, item.treatment, item.control) for item in self.contrasts
        }
        if observed_contrasts != expected_contrasts:
            raise ValueError("the frozen contrasts must be B7-B3, B7-B6, B8-B7, and B9-B7")

        expected_directions = {
            "critical_evidence_recall": ("automated", "higher"),
            "unnecessary_document_rate": ("automated", "lower"),
            "valid_chain_precision": ("automated", "higher"),
            "fact_chain_completeness": ("automated", "higher"),
            "evidence_obligation_completeness": ("automated", "higher"),
            "expert_acceptance": ("human", "higher"),
            "active_correction_time": ("human", "lower"),
            "severe_edit_count": ("human", "lower"),
        }
        observed_directions = {
            endpoint.endpoint_id: (endpoint.source, endpoint.direction)
            for endpoint in self.endpoints
        }
        if observed_directions != expected_directions:
            raise ValueError("endpoint set or benefit direction differs from the frozen design")

        known_contrasts = set(contrast_ids)
        known_endpoints = set(endpoint_ids)
        generated_ids: list[str] = []
        for family in self.multiplicity_families:
            if family.familywise_alpha != 0.05:
                raise ValueError("every multiplicity family must use alpha 0.05")
            if len(family.contrast_ids) != len(set(family.contrast_ids)):
                raise ValueError(f"{family.family_id} repeats a contrast")
            member_ids = [member.endpoint_id for member in family.members]
            if len(member_ids) != len(set(member_ids)):
                raise ValueError(f"{family.family_id} repeats an endpoint")
            if not set(family.contrast_ids).issubset(known_contrasts):
                raise ValueError(f"{family.family_id} references an unknown contrast")
            if not set(member_ids).issubset(known_endpoints):
                raise ValueError(f"{family.family_id} references an unknown endpoint")
            for member in family.members:
                source = next(
                    endpoint.source
                    for endpoint in self.endpoints
                    if endpoint.endpoint_id == member.endpoint_id
                )
                expected_method = (
                    "paired_case_bca_bootstrap"
                    if source == "automated"
                    else "crossed_case_reviewer_bootstrap"
                )
                if member.inference_method != expected_method:
                    raise ValueError(
                        f"{member.endpoint_id} does not use its frozen inference method"
                    )
            generated_ids.extend(
                hypothesis_id(family.family_id, contrast_id, endpoint_id)
                for contrast_id in family.contrast_ids
                for endpoint_id in member_ids
            )
        if len(generated_ids) != len(set(generated_ids)):
            raise ValueError("a hypothesis appears in more than one multiplicity family")

        family_shapes = {
            family.family_id: (
                family.role,
                set(family.contrast_ids),
                {member.endpoint_id: member.decision_rule for member in family.members},
            )
            for family in self.multiplicity_families
        }
        automated_rules = {
            "critical_evidence_recall": "superiority",
            "unnecessary_document_rate": "noninferiority",
            "valid_chain_precision": "superiority",
            "fact_chain_completeness": "superiority",
            "evidence_obligation_completeness": "superiority",
        }
        human_rules = {
            "expert_acceptance": "noninferiority",
            "active_correction_time": "noninferiority",
            "severe_edit_count": "noninferiority",
        }
        secondary_rules = {
            "critical_evidence_recall": "equivalence",
            "unnecessary_document_rate": "superiority",
            "valid_chain_precision": "superiority",
            "fact_chain_completeness": "equivalence",
            "evidence_obligation_completeness": "equivalence",
        }
        novelty_rules = {
            "critical_evidence_recall": "equivalence",
            "unnecessary_document_rate": "equivalence",
            "valid_chain_precision": "equivalence",
            "fact_chain_completeness": "equivalence",
            "evidence_obligation_completeness": "equivalence",
            "expert_acceptance": "noninferiority",
            "active_correction_time": "noninferiority",
            "severe_edit_count": "noninferiority",
        }
        expected_shapes = {
            "automated_primary": (
                "primary",
                {"b7_minus_b3", "b7_minus_b6"},
                automated_rules,
            ),
            "human_external_validity": (
                "optional_external_validity",
                {"b7_minus_b3", "b7_minus_b6"},
                human_rules,
            ),
            "b8_secondary": (
                "secondary",
                {"b8_minus_b7"},
                secondary_rules,
            ),
            "b9_novelty": (
                "secondary",
                {"b9_minus_b7"},
                {key: value for key, value in novelty_rules.items() if key not in human_rules},
            ),
            "b9_human_external_validity": (
                "optional_external_validity",
                {"b9_minus_b7"},
                human_rules,
            ),
        }
        if family_shapes != expected_shapes:
            raise ValueError("multiplicity families differ from the frozen hypothesis families")
        required_families = {
            family.family_id
            for family in self.multiplicity_families
            if family.required_for_confirmatory_decision
        }
        if required_families != {"automated_primary", "b8_secondary", "b9_novelty"}:
            raise ValueError("only autonomous families may be required for confirmatory decisions")

        human_ids = {
            endpoint.endpoint_id for endpoint in self.endpoints if endpoint.source == "human"
        }
        if set(self.reviewer_clustering.endpoint_ids) != human_ids:
            raise ValueError("reviewer clustering must cover every human endpoint")

        expected_headline = {
            hypothesis_id("automated_primary", contrast_id, endpoint_id)
            for contrast_id in ("b7_minus_b3", "b7_minus_b6")
            for endpoint_id in automated_rules
        }
        if set(self.headline_success.required_hypothesis_ids) != expected_headline:
            raise ValueError("headline success must join all autonomous primary tests")
        if len(self.headline_success.required_hypothesis_ids) != len(expected_headline):
            raise ValueError("headline success hypotheses must be unique")

        expected_novelty_kill = {
            hypothesis_id("b9_novelty", "b9_minus_b7", endpoint_id)
            for endpoint_id, (source, _) in expected_directions.items()
            if source == "automated"
        }
        if set(self.novelty_decision.kill_hypothesis_ids) != expected_novelty_kill:
            raise ValueError("novelty kill must join every autonomous B9-B7 test")
        if len(self.novelty_decision.kill_hypothesis_ids) != len(expected_novelty_kill):
            raise ValueError("novelty kill hypotheses must be unique")
        return self


class AnalysisFreezeReceipt(StrictModel):
    receipt_version: Literal["casepath.analysis-freeze-receipt/0.1.0"]
    spec_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    blinded_input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    codebook_commitment_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    frozen_at: datetime

    @model_validator(mode="after")
    def validate_timestamp(self) -> AnalysisFreezeReceipt:
        if self.frozen_at.tzinfo is None:
            raise ValueError("analysis freeze timestamp must include a timezone")
        return self


class BlindedPilotEndpointSummary(StrictModel):
    endpoint_token: str
    marginal_variance: float = Field(gt=0.0)
    within_case_correlation: float = Field(ge=-1.0, le=1.0)
    complete_pairs: int = Field(gt=1)


class BlindedPilotSummary(StrictModel):
    summary_version: Literal["casepath.blinded-pilot-summary/0.1.0"]
    pilot_case_count: int = Field(gt=1)
    endpoints: tuple[BlindedPilotEndpointSummary, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_summary(self) -> BlindedPilotSummary:
        tokens = [endpoint.endpoint_token for endpoint in self.endpoints]
        if any(not token for token in tokens) or len(tokens) != len(set(tokens)):
            raise ValueError("blinded pilot endpoint tokens must be nonempty and unique")
        if any(endpoint.complete_pairs > self.pilot_case_count for endpoint in self.endpoints):
            raise ValueError("complete pilot pairs cannot exceed the pilot case count")
        return self


class SampleSizeDecision(StrictModel):
    receipt_version: Literal["casepath.sample-size-decision/0.1.0"]
    blinded_pilot_summary_sha256: Sha256
    assumptions_sha256: Sha256
    maximum_paired_variance: float = Field(gt=0.0)
    complete_case_requirement: int = Field(gt=0)
    dropout_adjusted_requirement: int = Field(gt=0)
    rounding_multiple: int = Field(gt=0)
    final_case_count: int = Field(gt=0)


class ConditionCodebook(StrictModel):
    codebook_version: Literal["casepath.condition-codebook/0.1.0"]
    condition_to_arm: dict[ConditionId, str]
    unblinded_at: datetime

    @model_validator(mode="after")
    def validate_mapping(self) -> ConditionCodebook:
        if set(self.condition_to_arm) != {"B3", "B6", "B7", "B8", "B9"}:
            raise ValueError("condition codebook must map B3, B6, B7, B8, and B9")
        arms = tuple(self.condition_to_arm.values())
        if any(not arm for arm in arms) or len(arms) != len(set(arms)):
            raise ValueError("condition codebook arm IDs must be nonempty and unique")
        if self.unblinded_at.tzinfo is None:
            raise ValueError("codebook unblinding timestamp must include a timezone")
        return self


OutcomeStatus = Literal["observed", "missing", "system_failure", "review_failure"]


class RawAutomatedOutcome(StrictModel):
    case_id: str
    arm_id: str
    endpoint_id: str
    status: OutcomeStatus
    value: float | None = None

    @model_validator(mode="after")
    def validate_value(self) -> RawAutomatedOutcome:
        if (self.status == "observed") != (self.value is not None):
            raise ValueError("only observed outcomes may contain a value")
        if self.status == "review_failure":
            raise ValueError("automated outcomes cannot use review_failure")
        return self


class RawHumanOutcome(StrictModel):
    case_id: str
    arm_id: str
    reviewer_id: str
    endpoint_id: str
    status: OutcomeStatus
    value: float | None = None

    @model_validator(mode="after")
    def validate_value(self) -> RawHumanOutcome:
        if (self.status == "observed") != (self.value is not None):
            raise ValueError("only observed outcomes may contain a value")
        return self


class BlindedRawOutcomeBundle(StrictModel):
    bundle_version: Literal["casepath.blinded-raw-outcomes/0.1.0"]
    cohort_id: str
    split: Literal["confirmatory"]
    case_ids: tuple[str, ...] = Field(min_length=1)
    arm_ids: tuple[str, ...] = Field(min_length=2)
    reviewer_ids: tuple[str, ...] = ()
    automated: tuple[RawAutomatedOutcome, ...]
    human: tuple[RawHumanOutcome, ...]

    @model_validator(mode="after")
    def validate_id_sets(self) -> BlindedRawOutcomeBundle:
        for name, values in (
            ("case", self.case_ids),
            ("arm", self.arm_ids),
            ("reviewer", self.reviewer_ids),
        ):
            if any(not value for value in values) or len(values) != len(set(values)):
                raise ValueError(f"raw {name} IDs must be nonempty and unique")
        return self


class HypothesisEstimate(StrictModel):
    family_id: str
    treatment_arm_id: str
    control_arm_id: str
    endpoint_id: str
    estimate: float
    confidence_lower: float
    confidence_upper: float
    raw_p_value: float = Field(ge=0.0, le=1.0)
    inference_method: InferenceMethod
    endpoint_policy_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    analyzed_pairs: int = Field(ge=0)
    treatment_missing: int = Field(ge=0)
    control_missing: int = Field(ge=0)
    treatment_failures: int = Field(ge=0)
    control_failures: int = Field(ge=0)
    reviewer_clusters: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_interval(self) -> HypothesisEstimate:
        if not self.confidence_lower <= self.estimate <= self.confidence_upper:
            raise ValueError("estimate must fall inside its confidence interval")
        return self


class BlindedEstimateBundle(StrictModel):
    bundle_version: Literal["casepath.blinded-estimates/0.1.0"]
    spec_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    blinded_input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    cohort_id: str
    split: Literal["confirmatory"]
    case_count: int = Field(gt=0)
    estimates: tuple[HypothesisEstimate, ...]


class HypothesisDecision(StrictModel):
    hypothesis_id: str
    family_id: str
    contrast_id: str
    endpoint_id: str
    treatment: ConditionId
    control: ConditionId
    decision_rule: DecisionRule
    benefit_estimate: float
    benefit_lower: float
    benefit_upper: float
    margin: float
    margin_passed: bool
    raw_p_value: float
    holm_critical_alpha: float
    multiplicity_passed: bool
    passed: bool


class FamilyDecision(StrictModel):
    family_id: str
    hypothesis_ids: tuple[str, ...]
    passed_count: int = Field(ge=0)
    hypothesis_count: int = Field(gt=0)
    evidence_status: Literal["complete", "not_collected"]


class ConfirmatoryDecisionReceipt(StrictModel):
    receipt_version: Literal["casepath.confirmatory-decision/0.1.0"]
    spec_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    blinded_input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    codebook_commitment_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    decisions: tuple[HypothesisDecision, ...]
    families: tuple[FamilyDecision, ...]
    headline_required_hypothesis_ids: tuple[str, ...]
    headline_success: bool
    novelty_kill_hypothesis_ids: tuple[str, ...]
    novelty_kill_triggered: bool
    novelty_support_hypothesis_ids: tuple[str, ...]
    novelty_supported: bool


DomainFamily = Literal["mould_moisture", "rent_increase", "security_deposit"]


class StudyCaseRecord(StrictModel):
    case_id: str
    counterfactual_group_id: str
    domain_family: DomainFamily


class StudyPartitionManifest(StrictModel):
    partition_version: Literal["casepath.study-partition/0.1.0"]
    pilot_cases: tuple[StudyCaseRecord, ...]
    confirmatory_cases: tuple[StudyCaseRecord, ...]

    @model_validator(mode="after")
    def validate_partition(self) -> StudyPartitionManifest:
        pilot_ids = [case.case_id for case in self.pilot_cases]
        confirmatory_ids = [case.case_id for case in self.confirmatory_cases]
        if len(pilot_ids) != 30 or len(confirmatory_ids) != 60:
            raise ValueError("study partition requires 30 pilot and 60 confirmatory cases")
        if len(pilot_ids) != len(set(pilot_ids)) or len(confirmatory_ids) != len(
            set(confirmatory_ids)
        ):
            raise ValueError("case IDs must be unique within each study split")
        if set(pilot_ids).intersection(confirmatory_ids):
            raise ValueError("pilot and confirmatory case IDs must be disjoint")
        pilot_groups = {case.counterfactual_group_id for case in self.pilot_cases}
        confirmatory_groups = {case.counterfactual_group_id for case in self.confirmatory_cases}
        if "" in pilot_groups or "" in confirmatory_groups:
            raise ValueError("counterfactual group IDs must be nonempty")
        if pilot_groups.intersection(confirmatory_groups):
            raise ValueError("pilot and confirmatory counterfactual groups must be disjoint")
        expected_counts = {
            "pilot": 10,
            "confirmatory": 20,
        }
        for split_name, cases in (
            ("pilot", self.pilot_cases),
            ("confirmatory", self.confirmatory_cases),
        ):
            counts = {
                domain: sum(case.domain_family == domain for case in cases)
                for domain in ("mould_moisture", "rent_increase", "security_deposit")
            }
            if set(counts.values()) != {expected_counts[split_name]}:
                raise ValueError(f"{split_name} cases must be balanced across domains")
        return self


class StudyLockReceipt(StrictModel):
    receipt_version: Literal["casepath.study-lock/0.1.0"]
    study_id: str
    locked_at: datetime
    analysis_plan_sha256: Sha256
    analysis_code_sha256: Sha256
    prompt_bundle_sha256: Sha256
    evaluator_sha256: Sha256
    model_revision: str
    runtime_image_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    benchmark_sha256: Sha256
    benchmark_authority: Literal["immutable_compiled_oracle"]
    cohort_schedule_sha256: Sha256
    cohort_case_count: Literal[60]
    human_review_protocol_sha256: Sha256 | None = None
    condition_codebook_commitment_sha256: Sha256
    study_partition_sha256: Sha256
    pilot_case_count: Literal[30]
    confirmatory_case_count: Literal[60]
    confirmatory_calls_prohibited_before_lock: Literal[True]

    @model_validator(mode="after")
    def validate_lock(self) -> StudyLockReceipt:
        if not self.study_id or not self.model_revision:
            raise ValueError("study lock identity fields must be nonempty")
        if self.locked_at.tzinfo is None:
            raise ValueError("study lock timestamp must include a timezone")
        return self
