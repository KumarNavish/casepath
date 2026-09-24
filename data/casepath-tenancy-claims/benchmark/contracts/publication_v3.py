"""Single source of truth for publication-v3 execution.

The final study lock is deliberately broad.  A runner may validate additional
suite-local receipts, but it may not construct a paid provider unless it also
validates this exact lock and every field relevant to that suite.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field, model_validator

from manifests.digests import digest_json

from .schema import StrictModel

Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


def primary_backbone_identity_sha256(model_id: str) -> str:
    """Hash the shared weights identity without conflating it with a route."""

    if not model_id:
        raise ValueError("primary backbone model ID must be nonempty")
    return digest_json({"model_id": model_id})


def canary_protocol_bundle_sha256(*, custom: str, paged: str, worf: str, tau2: str) -> str:
    """Hash the exact ordered protocols authorized for route canaries."""

    return digest_json({"custom": custom, "paged": paged, "worf": worf, "tau2": tau2})


def canary_prompt_bundle_sha256(*, custom: str, paged: str, worf: str, tau2_agent: str) -> str:
    """Hash every prompt identity explicitly present in the final study lock."""

    return digest_json({"custom": custom, "paged": paged, "worf": worf, "tau2_agent": tau2_agent})


CanaryRoleV3 = Literal[
    "together_agent",
    "openai_user_simulator",
    "openai_native_judge",
]
SpendSuiteIdV3 = Literal["custom", "paged", "worf", "tau2"]
SpendLedgerStateV3 = Literal["available", "reserved", "terminal", "incident"]


class PublicNativeBenchmarkAdmissionV3(StrictModel):
    """Content-pinned, zero-network admission for one external benchmark."""

    benchmark_id: Literal[
        "paged-acl2024-test",
        "worfbench-iclr2025-test",
        "tau2-bench-v1.0.1-core",
    ]
    manifest_sha256: Sha256
    repository_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    dataset_revision: str | None
    checked_file_count: int = Field(ge=1)
    released_row_or_task_count: int = Field(ge=1)
    repository_license_spdx: Literal["Apache-2.0", "MIT"]
    dataset_license_spdx: Literal["Apache-2.0", "MIT"]
    native_evaluator_file_set_sha256: Sha256
    eligible: Literal[True]
    blockers: tuple[()] = ()


class PublicNativeSuiteReceiptV3(StrictModel):
    """Audited external-suite identity used by every public-native protocol."""

    contract: Literal["casepath.public-native-suite-receipt/3.0.0"]
    admissions: tuple[
        PublicNativeBenchmarkAdmissionV3,
        PublicNativeBenchmarkAdmissionV3,
        PublicNativeBenchmarkAdmissionV3,
    ]
    native_inputs_preserved: Literal[True]
    native_evaluators_preserved: Literal[True]
    gold_excluded_from_model_boundary: Literal[True]
    runtime_model_calls: Literal[0]
    receipt_sha256: Sha256

    @model_validator(mode="after")
    def validate_receipt(self) -> PublicNativeSuiteReceiptV3:
        expected = (
            "paged-acl2024-test",
            "worfbench-iclr2025-test",
            "tau2-bench-v1.0.1-core",
        )
        if tuple(row.benchmark_id for row in self.admissions) != expected:
            raise ValueError("public-native suite admissions are absent or out of order")
        if self.receipt_sha256 != digest_json(
            self.model_dump(mode="json", exclude={"receipt_sha256"})
        ):
            raise ValueError("public-native suite receipt hash is stale")
        return self


class PublicNativeProtocolFreezeReceiptV3(StrictModel):
    """One zero-network receipt for every durable public-native protocol artifact."""

    contract: Literal["casepath.public-native-protocol-freeze/3.0.0"]
    public_native_suite_receipt_sha256: Sha256
    runtime_image_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    cross_suite_spend_manifest_sha256: Sha256
    paged_protocol_sha256: Sha256
    paged_schedule_sha256: Sha256
    paged_row_count: Literal[1154]
    paged_expected_calls: Literal[5770]
    worf_protocol_sha256: Sha256
    worf_schedule_sha256: Sha256
    worf_row_count: Literal[2146]
    worf_expected_calls: Literal[10730]
    tau2_protocol_sha256: Sha256
    tau2_repository_sha256: Sha256
    tau2_schedule_sha256: Sha256
    tau2_task_count: Literal[278]
    tau2_trial_count: Literal[3336]
    tau2_agent_prompt_sha256: Sha256
    tau2_evaluator_sha256: Sha256
    runtime_model_calls: Literal[0]
    receipt_sha256: Sha256

    @model_validator(mode="after")
    def validate_receipt(self) -> PublicNativeProtocolFreezeReceiptV3:
        if self.receipt_sha256 != digest_json(
            self.model_dump(mode="json", exclude={"receipt_sha256"})
        ):
            raise ValueError("public-native protocol-freeze receipt hash is stale")
        return self


class PublicationFailurePolicyV3(StrictModel):
    """Typed custom-study failure policy; prose or opaque hashes are inadmissible."""

    contract: Literal["casepath.custom-failure-policy/3.0.0"]
    primary_population: Literal["all_90_locked_hidden_test_cases"]
    higher_is_better_missing_or_failure_score: float = Field(ge=0.0, le=0.0)
    lower_is_better_missing_or_failure_score: float = Field(ge=1.0, le=1.0)
    unknown_dispatch_policy: Literal["never_reissue_score_worst"]
    complete_case_role: Literal["sensitivity_only_cannot_rescue"]
    malformed_candidate_policy: Literal["system_failure_score_worst"]
    contrast_failure_policy: Literal["one_sided_lower_support_two_sided_null"]
    policy_sha256: Sha256

    @model_validator(mode="after")
    def validate_policy(self) -> PublicationFailurePolicyV3:
        if (
            self.higher_is_better_missing_or_failure_score,
            self.lower_is_better_missing_or_failure_score,
        ) != (0.0, 1.0):
            raise ValueError("custom failure-policy scores must be the frozen worst values")
        if self.policy_sha256 != digest_json(
            self.model_dump(mode="json", exclude={"policy_sha256"})
        ):
            raise ValueError("custom failure-policy hash is stale")
        return self


class SimulationFamilyResultV3(StrictModel):
    family_id: str = Field(min_length=1)
    hypothesis_count: int = Field(ge=1)
    familywise_alpha: float = Field(gt=0.0, le=0.05)
    null_fwer: float = Field(ge=0.0, le=1.0)
    null_fwer_upper_95: float = Field(ge=0.0, le=1.0)
    missingness_null_fwer: float = Field(ge=0.0, le=1.0)
    missingness_null_fwer_upper_95: float = Field(ge=0.0, le=1.0)
    maximum_allowed_fwer: float = Field(gt=0.0, le=0.1)
    passed: bool

    @model_validator(mode="after")
    def validate_decision(self) -> SimulationFamilyResultV3:
        expected_alpha = 0.04 if self.family_id == "order_headline" else 0.05
        expected_maximum = expected_alpha + 0.02
        if self.familywise_alpha != expected_alpha or self.maximum_allowed_fwer != expected_maximum:
            raise ValueError("simulation family thresholds differ from the frozen policy")
        if (
            self.null_fwer_upper_95 < self.null_fwer
            or self.missingness_null_fwer_upper_95 < self.missingness_null_fwer
        ):
            raise ValueError("simulation FWER upper confidence bounds are invalid")
        if self.passed != (
            self.null_fwer_upper_95 <= self.maximum_allowed_fwer
            and self.missingness_null_fwer_upper_95 <= self.maximum_allowed_fwer
        ):
            raise ValueError("simulation family decision fields disagree")
        return self


class SimulationHypothesisResultV3(StrictModel):
    hypothesis_id: str = Field(min_length=1)
    family_id: str = Field(min_length=1)
    null_interval_coverage: float = Field(ge=0.0, le=1.0)
    null_interval_coverage_lower_95: float = Field(ge=0.0, le=1.0)
    null_interval_coverage_upper_95: float = Field(ge=0.0, le=1.0)
    target_effect: float = Field(gt=0.0)
    target_power: float = Field(ge=0.0, le=1.0)
    target_power_lower_95: float = Field(ge=0.0, le=1.0)
    minimum_coverage: float = Field(ge=0.9, le=1.0)
    maximum_coverage: float = Field(ge=0.9, le=1.0)
    minimum_power: float = Field(ge=0.0, le=1.0)
    passed: bool

    @model_validator(mode="after")
    def validate_decision(self) -> SimulationHypothesisResultV3:
        if (
            self.target_effect,
            self.minimum_coverage,
            self.maximum_coverage,
            self.minimum_power,
        ) != (0.12, 0.925, 0.975, 0.80):
            raise ValueError("simulation hypothesis thresholds differ from the frozen policy")
        if (
            not (
                self.null_interval_coverage_lower_95
                <= self.null_interval_coverage
                <= self.null_interval_coverage_upper_95
            )
            or self.target_power_lower_95 > self.target_power
        ):
            raise ValueError("simulation hypothesis confidence bounds are invalid")
        expected = (
            self.null_interval_coverage_lower_95 >= self.minimum_coverage
            and self.null_interval_coverage_upper_95 <= self.maximum_coverage
            and self.target_power_lower_95 >= self.minimum_power
        )
        if self.passed != expected:
            raise ValueError("simulation hypothesis decision fields disagree")
        return self


class StatisticalSimulationReceiptV3(StrictModel):
    """Outcome-blind operating-characteristic audit for the exact V3 geometry."""

    contract: Literal["casepath.custom-factorial-simulation/3.0.0"]
    protocol_sha256: Sha256
    cohort_sha256: Sha256
    analysis_code_sha256: Sha256
    simulation_code_sha256: Sha256
    seed: int = Field(ge=0)
    repetitions: int = Field(ge=4000)
    hidden_case_count: Literal[90]
    hidden_family_count: Literal[17]
    tenancy_subdomain_count: Literal[3]
    hypothesis_count: Literal[40]
    family_count: Literal[5]
    cluster_geometry: Literal[
        "equal_case_within_family_equal_family_within_subdomain_equal_subdomain"
    ]
    null_data_generating_process: Literal[
        "gaussian_family_random_effect_plus_case_residual_at_each_frozen_decision_boundary"
    ]
    target_effect: float = Field(gt=0.0)
    family_standard_deviation: float = Field(gt=0.0)
    case_standard_deviation: float = Field(gt=0.0)
    missingness_pattern: Literal[
        "deterministic_ten_percent_case_failures_scored_at_the_frozen_contrast_conservative_value"
    ]
    family_results: tuple[SimulationFamilyResultV3, ...] = Field(min_length=5, max_length=5)
    hypothesis_results: tuple[SimulationHypothesisResultV3, ...] = Field(
        min_length=40, max_length=40
    )
    independent_verifier_code_sha256: Sha256
    independent_reference_summary_sha256: Sha256
    independent_verification_scope: Literal[
        "rng_family_case_geometry_estimator_decisions_holm_wilson_reimplemented_shared_student_t_kernel"
    ]
    independent_family_result_match_count: Literal[5]
    independent_hypothesis_result_match_count: Literal[40]
    independent_reported_value_match_count: Literal[525]
    independent_replay_passed: Literal[True]
    all_acceptance_thresholds_passed: Literal[True]
    runtime_model_calls: Literal[0]
    receipt_sha256: Sha256

    @model_validator(mode="after")
    def validate_receipt(self) -> StatisticalSimulationReceiptV3:
        endpoints = {
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
        }
        headline = {
            "H-ORDER-PATH",
            "H-ORDER-BRANCH",
            "H-ORDER-CER",
            "H-ORDER-UDR",
        }
        mechanism = {
            *(
                f"M-ORDER-{endpoint}"
                for endpoint in endpoints
                - {
                    "behavioral_valid_path_rate",
                    "branch_predicate_accuracy",
                    "critical_evidence_recall",
                    "unnecessary_document_rate",
                }
            ),
            *(f"M-REP-{endpoint}" for endpoint in endpoints),
            *(f"M-INTERACTION-{endpoint}" for endpoint in endpoints),
        }
        expected_membership = {
            **{item: "order_headline" for item in headline},
            **{item: "factorial_mechanism" for item in mechanism},
            "F-VERIFY-CER": "verifier_falsification",
            "F-VERIFY-UDR": "verifier_falsification",
            "F-VERIFY-CHAIN": "verifier_falsification",
            "F-EXIDE-CER": "exide_falsification",
            "F-EXIDE-UDR": "exide_falsification",
            "F-DOCFIRST-PATH": "document_first_falsification",
            "F-DOCFIRST-CER": "document_first_falsification",
        }
        family_counts = {
            "order_headline": 4,
            "factorial_mechanism": 29,
            "verifier_falsification": 3,
            "exide_falsification": 2,
            "document_first_falsification": 2,
        }
        if {item.family_id: item.hypothesis_count for item in self.family_results} != family_counts:
            raise ValueError("simulation receipt has the wrong multiplicity-family roster")
        observed_membership = {
            item.hypothesis_id: item.family_id for item in self.hypothesis_results
        }
        if observed_membership != expected_membership:
            raise ValueError("simulation receipt has the wrong hypothesis roster or membership")
        if (
            self.target_effect,
            self.family_standard_deviation,
            self.case_standard_deviation,
        ) != (0.12, 0.06, 0.10):
            raise ValueError("simulation data-generating parameters differ from the freeze")
        if not all(item.passed for item in self.family_results) or not all(
            item.passed for item in self.hypothesis_results
        ):
            raise ValueError("simulation receipt claims acceptance despite a failed threshold")
        if self.receipt_sha256 != digest_json(
            self.model_dump(mode="json", exclude={"receipt_sha256"})
        ):
            raise ValueError("factorial simulation receipt hash is stale")
        return self


class SuiteSpendLimitV3(StrictModel):
    suite_id: SpendSuiteIdV3
    budget_sha256: Sha256
    max_provider_calls: int = Field(ge=1)
    max_input_tokens: int = Field(ge=1)
    max_output_tokens: int = Field(ge=1)
    max_cost_microusd: int = Field(ge=1)


class CrossSuiteSpendManifestV3(StrictModel):
    """One exact, reviewable upper bound for every paid publication run."""

    contract: Literal["casepath.cross-suite-spend-manifest/3.0.0"]
    price_bundle_sha256: Sha256
    suites: tuple[
        SuiteSpendLimitV3,
        SuiteSpendLimitV3,
        SuiteSpendLimitV3,
        SuiteSpendLimitV3,
    ]
    canary_max_cost_microusd: int = Field(ge=1)
    evaluation_max_cost_microusd: int = Field(ge=1)
    global_max_cost_microusd: int = Field(ge=1)
    spend_manifest_sha256: Sha256

    @model_validator(mode="after")
    def validate_manifest(self) -> CrossSuiteSpendManifestV3:
        if tuple(item.suite_id for item in self.suites) != (
            "custom",
            "paged",
            "worf",
            "tau2",
        ):
            raise ValueError("cross-suite spend rows are absent, repeated, or out of order")
        expected_evaluation = sum(item.max_cost_microusd for item in self.suites)
        if self.evaluation_max_cost_microusd != expected_evaluation:
            raise ValueError("cross-suite evaluation cost does not equal the suite caps")
        if self.global_max_cost_microusd != (expected_evaluation + self.canary_max_cost_microusd):
            raise ValueError("cross-suite global cost does not include evaluations and canaries")
        if self.spend_manifest_sha256 != digest_json(
            self.model_dump(mode="json", exclude={"spend_manifest_sha256"})
        ):
            raise ValueError("cross-suite spend manifest hash is stale")
        return self

    def for_suite(self, suite_id: SpendSuiteIdV3) -> SuiteSpendLimitV3:
        return next(item for item in self.suites if item.suite_id == suite_id)


class CrossSuiteSpendLedgerEntryV3(StrictModel):
    suite_id: SpendSuiteIdV3
    budget_sha256: Sha256
    maximum_cost_microusd: int = Field(ge=1)
    state: SpendLedgerStateV3
    lease_id: Sha256 | None = None
    output_root_sha256: Sha256 | None = None
    journal_set_sha256: Sha256 | None = None
    observed_cost_microusd: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_state(self) -> CrossSuiteSpendLedgerEntryV3:
        if self.state == "available":
            if any(
                value is not None
                for value in (
                    self.lease_id,
                    self.output_root_sha256,
                    self.journal_set_sha256,
                    self.observed_cost_microusd,
                )
            ):
                raise ValueError("available spend rows cannot retain a lease or usage")
        elif self.state == "reserved":
            if (
                self.lease_id is None
                or self.output_root_sha256 is None
                or self.journal_set_sha256 is not None
                or self.observed_cost_microusd is not None
            ):
                raise ValueError("reserved spend rows require one unspent output-root lease")
        else:
            if (
                self.lease_id is None
                or self.output_root_sha256 is None
                or self.journal_set_sha256 is None
                or self.observed_cost_microusd is None
            ):
                raise ValueError("terminal spend rows require lease, journal, and measured cost")
            expected_state = (
                "terminal"
                if self.observed_cost_microusd <= self.maximum_cost_microusd
                else "incident"
            )
            if self.state != expected_state:
                raise ValueError("terminal/incident state disagrees with measured suite cost")
        return self


class CrossSuiteSpendLedgerV3(StrictModel):
    """One global, crash-safe publication lease shared by all four suites."""

    contract: Literal["casepath.cross-suite-spend-ledger/3.0.0"]
    study_lock_sha256: Sha256
    pre_canary_receipt_sha256: Sha256
    finalization_receipt_sha256: Sha256
    spend_manifest_sha256: Sha256
    canary_cost_microusd: int = Field(ge=0)
    canary_max_cost_microusd: int = Field(ge=1)
    suites: tuple[
        CrossSuiteSpendLedgerEntryV3,
        CrossSuiteSpendLedgerEntryV3,
        CrossSuiteSpendLedgerEntryV3,
        CrossSuiteSpendLedgerEntryV3,
    ]
    reserved_or_spent_cost_microusd: int = Field(ge=0)
    global_max_cost_microusd: int = Field(ge=1)
    caps_respected: bool
    ledger_sha256: Sha256

    @model_validator(mode="after")
    def validate_ledger(self) -> CrossSuiteSpendLedgerV3:
        if tuple(row.suite_id for row in self.suites) != ("custom", "paged", "worf", "tau2"):
            raise ValueError("global spend-ledger suite roster is absent or out of order")
        suite_cost = sum(
            (
                row.maximum_cost_microusd
                if row.state == "reserved"
                else (row.observed_cost_microusd or 0)
            )
            for row in self.suites
        )
        expected_total = self.canary_cost_microusd + suite_cost
        if self.reserved_or_spent_cost_microusd != expected_total:
            raise ValueError("global spend-ledger total differs from leases and measured usage")
        expected_caps = (
            self.canary_cost_microusd <= self.canary_max_cost_microusd
            and expected_total <= self.global_max_cost_microusd
            and all(row.state != "incident" for row in self.suites)
        )
        if self.caps_respected != expected_caps:
            raise ValueError("global spend-ledger cap decision differs")
        if self.ledger_sha256 != digest_json(
            self.model_dump(mode="json", exclude={"ledger_sha256"})
        ):
            raise ValueError("global spend-ledger hash is stale")
        return self

    def for_suite(self, suite_id: SpendSuiteIdV3) -> CrossSuiteSpendLedgerEntryV3:
        return next(item for item in self.suites if item.suite_id == suite_id)


class CanaryRoleModelV3(StrictModel):
    role: CanaryRoleV3
    provider: Literal["Together", "OpenAI"]
    model_id: str = Field(min_length=1)
    model_revision: str = Field(min_length=1)


class CanaryModelBundleV3(StrictModel):
    """Canonical ordered model identity used by canary authorization."""

    contract: Literal["casepath.canary-model-bundle/3.0.0"]
    roles: tuple[CanaryRoleModelV3, CanaryRoleModelV3, CanaryRoleModelV3]
    bundle_sha256: Sha256

    @model_validator(mode="after")
    def validate_bundle(self) -> CanaryModelBundleV3:
        expected_roles = (
            ("together_agent", "Together"),
            ("openai_user_simulator", "OpenAI"),
            ("openai_native_judge", "OpenAI"),
        )
        if tuple((item.role, item.provider) for item in self.roles) != expected_roles:
            raise ValueError("canary model roles or providers are not in canonical order")
        expected = digest_json(self.model_dump(mode="json", exclude={"bundle_sha256"}))
        if self.bundle_sha256 != expected:
            raise ValueError("canary model bundle hash is stale")
        return self


class CanaryRoleRouteV3(StrictModel):
    role: CanaryRoleV3
    provider: Literal["Together", "OpenAI"]
    endpoint: str = Field(pattern=r"^https://")
    route_id: str = Field(min_length=1)
    fallback_allowed: Literal[False]


class CanaryRouteBundleV3(StrictModel):
    contract: Literal["casepath.canary-route-bundle/3.0.0"]
    roles: tuple[CanaryRoleRouteV3, CanaryRoleRouteV3, CanaryRoleRouteV3]
    bundle_sha256: Sha256

    @model_validator(mode="after")
    def validate_bundle(self) -> CanaryRouteBundleV3:
        expected_roles = (
            ("together_agent", "Together"),
            ("openai_user_simulator", "OpenAI"),
            ("openai_native_judge", "OpenAI"),
        )
        if tuple((item.role, item.provider) for item in self.roles) != expected_roles:
            raise ValueError("canary routes are not in canonical order")
        expected = digest_json(self.model_dump(mode="json", exclude={"bundle_sha256"}))
        if self.bundle_sha256 != expected:
            raise ValueError("canary route bundle hash is stale")
        return self


class CanaryRolePriceV3(StrictModel):
    role: CanaryRoleV3
    provider: Literal["Together", "OpenAI"]
    currency: Literal["USD"]
    input_usd_per_million_tokens: float = Field(gt=0.0)
    output_usd_per_million_tokens: float = Field(gt=0.0)
    observed_on: str = Field(pattern=r"^20[0-9]{2}-[0-9]{2}-[0-9]{2}$")
    price_source_url: str = Field(pattern=r"^https://")
    price_source_sha256: Sha256


class CanaryPriceBundleV3(StrictModel):
    contract: Literal["casepath.canary-price-bundle/3.0.0"]
    roles: tuple[CanaryRolePriceV3, CanaryRolePriceV3, CanaryRolePriceV3]
    bundle_sha256: Sha256

    @model_validator(mode="after")
    def validate_bundle(self) -> CanaryPriceBundleV3:
        expected_roles = (
            ("together_agent", "Together"),
            ("openai_user_simulator", "OpenAI"),
            ("openai_native_judge", "OpenAI"),
        )
        if tuple((item.role, item.provider) for item in self.roles) != expected_roles:
            raise ValueError("canary prices are not in canonical order")
        expected = digest_json(self.model_dump(mode="json", exclude={"bundle_sha256"}))
        if self.bundle_sha256 != expected:
            raise ValueError("canary price bundle hash is stale")
        return self


class CanaryAuthorizationV3(StrictModel):
    """Outcome-blind authorization for the three excluded route canaries."""

    contract: Literal["casepath.canary-authorization/3.0.0"]
    study_id: Literal["casepath-publication-v3"]
    status: Literal["canary_only"]
    protocol_bundle_sha256: Sha256
    model_bundle_sha256: Sha256
    prompt_bundle_sha256: Sha256
    provider_route_bundle_sha256: Sha256
    price_bundle_sha256: Sha256
    runtime_image_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    canary_roles: tuple[
        Literal["together_agent"],
        Literal["openai_user_simulator"],
        Literal["openai_native_judge"],
    ]
    canary_case_ids: tuple[str, str, str]
    evaluation_case_overlap: Literal[False]
    maximum_total_cost_microusd: int = Field(ge=1)
    expires_at: datetime
    post_canary_policy: Literal["freeze_final_study_lock_or_stop"]
    authorization_sha256: Sha256

    @model_validator(mode="after")
    def validate_authorization(self) -> CanaryAuthorizationV3:
        if self.expires_at.tzinfo is None:
            raise ValueError("canary authorization expiry must include a timezone")
        if self.canary_roles != (
            "together_agent",
            "openai_user_simulator",
            "openai_native_judge",
        ):
            raise ValueError("publication v3 requires exactly three route canaries")
        if len(set(self.canary_case_ids)) != 3:
            raise ValueError("canary case IDs must be distinct")
        expected = digest_json(self.model_dump(mode="json", exclude={"authorization_sha256"}))
        if self.authorization_sha256 != expected:
            raise ValueError("canary authorization hash is stale")
        return self


class PublicationPreCanaryReceiptV3(StrictModel):
    """Outcome-blind freeze that must exist before any route canary is sent."""

    contract: Literal["casepath.publication-pre-canary-freeze/3.0.0"]
    custom_protocol_sha256: Sha256
    paged_protocol_sha256: Sha256
    worf_protocol_sha256: Sha256
    tau2_protocol_sha256: Sha256
    custom_prompt_sha256: Sha256
    paged_prompt_sha256: Sha256
    worf_prompt_sha256: Sha256
    tau2_agent_prompt_sha256: Sha256
    model_bundle: CanaryModelBundleV3
    route_bundle: CanaryRouteBundleV3
    price_bundle: CanaryPriceBundleV3
    spend_manifest: CrossSuiteSpendManifestV3
    authorization: CanaryAuthorizationV3
    runtime_model_calls: Literal[0]
    receipt_sha256: Sha256

    @model_validator(mode="after")
    def validate_receipt(self) -> PublicationPreCanaryReceiptV3:
        if self.authorization.protocol_bundle_sha256 != canary_protocol_bundle_sha256(
            custom=self.custom_protocol_sha256,
            paged=self.paged_protocol_sha256,
            worf=self.worf_protocol_sha256,
            tau2=self.tau2_protocol_sha256,
        ):
            raise ValueError("pre-canary authorization does not bind the four protocols")
        if self.authorization.prompt_bundle_sha256 != canary_prompt_bundle_sha256(
            custom=self.custom_prompt_sha256,
            paged=self.paged_prompt_sha256,
            worf=self.worf_prompt_sha256,
            tau2_agent=self.tau2_agent_prompt_sha256,
        ):
            raise ValueError("pre-canary authorization does not bind the four prompts")
        if (
            self.authorization.model_bundle_sha256 != self.model_bundle.bundle_sha256
            or self.authorization.provider_route_bundle_sha256 != self.route_bundle.bundle_sha256
            or self.authorization.price_bundle_sha256 != self.price_bundle.bundle_sha256
            or self.spend_manifest.price_bundle_sha256 != self.price_bundle.bundle_sha256
            or self.authorization.maximum_total_cost_microusd
            != self.spend_manifest.canary_max_cost_microusd
        ):
            raise ValueError("pre-canary model, route, price, or spend bindings differ")
        if self.receipt_sha256 != digest_json(
            self.model_dump(mode="json", exclude={"receipt_sha256"})
        ):
            raise ValueError("pre-canary freeze receipt hash is stale")
        return self


class RouteCanaryReceiptV3(StrictModel):
    """One excluded paid call proving an exact model, route, and price boundary."""

    contract: Literal["casepath.route-canary-receipt/3.0.0"]
    authorization_sha256: Sha256
    model_bundle_sha256: Sha256
    route_bundle_sha256: Sha256
    price_bundle_sha256: Sha256
    role: CanaryRoleV3
    case_id: str = Field(min_length=1)
    evaluation_case_overlap: Literal[False]
    provider: Literal["Together", "OpenAI"]
    model_id: str = Field(min_length=1)
    model_revision: str = Field(min_length=1)
    route_id: str = Field(min_length=1)
    provider_request_id: str = Field(min_length=1)
    provider_response_model: str = Field(min_length=1)
    provider_response_route: str = Field(min_length=1)
    request_sha256: Sha256
    response_sha256: Sha256
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    reported_cost_microusd: int | None = Field(default=None, ge=0)
    derived_cost_microusd: int = Field(ge=0)
    successful_provider_calls: Literal[1]
    status: Literal["succeeded"]
    executed_at: datetime
    receipt_sha256: Sha256

    @model_validator(mode="after")
    def validate_receipt(self) -> RouteCanaryReceiptV3:
        if self.executed_at.tzinfo is None:
            raise ValueError("route canary timestamp must include a timezone")
        expected_provider = "Together" if self.role == "together_agent" else "OpenAI"
        if self.provider != expected_provider:
            raise ValueError("route canary role uses the wrong provider")
        if self.provider == "Together" and self.reported_cost_microusd is None:
            raise ValueError("Together canary must preserve provider-reported cost")
        expected = digest_json(self.model_dump(mode="json", exclude={"receipt_sha256"}))
        if self.receipt_sha256 != expected:
            raise ValueError("route canary receipt hash is stale")
        return self


class PublicationFinalizationReceiptV3(StrictModel):
    """Zero-call proof that paid canaries were excluded and the final lock is coherent."""

    contract: Literal["casepath.publication-finalization/3.0.0"]
    pre_canary_receipt_sha256: Sha256
    study_lock_sha256: Sha256
    canary_receipt_set_sha256: Sha256
    together_agent_canary_receipt_sha256: Sha256
    openai_user_canary_receipt_sha256: Sha256
    openai_judge_canary_receipt_sha256: Sha256
    total_canary_cost_microusd: int = Field(ge=0)
    maximum_canary_cost_microusd: int = Field(ge=1)
    canaries_excluded_from_all_outcomes: Literal[True]
    final_lock_frozen_after_canaries: Literal[True]
    runtime_model_calls: Literal[0]
    receipt_sha256: Sha256

    @model_validator(mode="after")
    def validate_receipt(self) -> PublicationFinalizationReceiptV3:
        if self.total_canary_cost_microusd > self.maximum_canary_cost_microusd:
            raise ValueError("route canaries exceed the preauthorized cap")
        if self.receipt_sha256 != digest_json(
            self.model_dump(mode="json", exclude={"receipt_sha256"})
        ):
            raise ValueError("publication finalization receipt hash is stale")
        return self


class PublicationOneLockAdmissionReceiptV3(StrictModel):
    """Proof that all four zero-call admissions resolved the same final lock."""

    contract: Literal["casepath.publication-one-lock-admission/3.0.0"]
    study_lock_sha256: Sha256
    finalization_receipt_sha256: Sha256
    spend_ledger_sha256: Sha256
    custom_protocol_sha256: Sha256
    custom_admission_binding_sha256: Sha256
    paged_protocol_sha256: Sha256
    paged_admission_sha256: Sha256
    worf_protocol_sha256: Sha256
    worf_admission_sha256: Sha256
    tau2_protocol_sha256: Sha256
    tau2_admission_sha256: Sha256
    all_suite_admissions_share_lock: Literal[True]
    global_spend_ledger_unspent: Literal[True]
    eligible: Literal[True]
    runtime_model_calls: Literal[0]
    receipt_sha256: Sha256

    @model_validator(mode="after")
    def validate_receipt(self) -> PublicationOneLockAdmissionReceiptV3:
        if self.receipt_sha256 != digest_json(
            self.model_dump(mode="json", exclude={"receipt_sha256"})
        ):
            raise ValueError("one-lock admission receipt hash is stale")
        return self


class CustomModelInputBundleReceiptV3(StrictModel):
    """Exact all-arm custom input bundle, including copyable source locators."""

    contract: Literal["casepath.custom-model-input-bundle/3.0.0"]
    public_manifest_sha256: Sha256
    prompt_template_sha256: Sha256
    projection_contract: Literal["casepath.text-model-projection/3.0.0"]
    projection_identity: Literal["python-3.13-email+pypdf-6.10.0+jpeg-opaque/1.0.0"]
    closed_vocabulary_ontology_contract: Literal["casepath.closed-vocabulary-ontology/1.0.0"]
    closed_vocabulary_ontology_sha256: Sha256
    source_registry_file_set_sha256: Sha256
    projected_input_file_set_sha256: Sha256
    projected_case_count: Literal[150]
    source_registry_case_count: Literal[150]
    forbidden_evaluator_field_count: Literal[0]
    bundle_sha256: Sha256

    @model_validator(mode="after")
    def validate_bundle(self) -> CustomModelInputBundleReceiptV3:
        expected = digest_json(self.model_dump(mode="json", exclude={"bundle_sha256"}))
        if self.bundle_sha256 != expected:
            raise ValueError("custom v3 model-input bundle hash is stale")
        return self


class PublicationStudyLockV3(StrictModel):
    """Final immutable lock shared by custom, PAGED, WorF, and tau2 runners."""

    contract: Literal["casepath.publication-study-lock/3.0.0"]
    study_id: Literal["casepath-publication-v3"]
    status: Literal["locked_for_production"]
    locked_at: datetime
    claim_scope: Literal["casepath_benchmark_and_public_native_coprimary"]

    # Public CasePath benchmark and its independently replayed evaluator.
    custom_protocol_sha256: Sha256
    custom_cohort_sha256: Sha256
    custom_compiler_receipt_sha256: Sha256
    custom_oracle_audit_receipt_sha256: Sha256
    custom_leakage_audit_receipt_sha256: Sha256
    custom_analysis_code_sha256: Sha256
    custom_evaluator_bundle_sha256: Sha256
    custom_schedule_sha256: Sha256
    custom_prompt_bundle_sha256: Sha256
    custom_model_input_bundle_sha256: Sha256
    custom_release_decision_sha256: Sha256
    custom_release_manifest_sha256: Sha256
    custom_release_gate_receipt_sha256: Sha256
    custom_leaderboard_protocol_sha256: Sha256

    # PAGED native evaluation.
    paged_protocol_sha256: Sha256
    paged_data_sha256: Sha256
    paged_adapter_sha256: Sha256
    paged_prompt_sha256: Sha256
    paged_evaluator_sha256: Sha256
    paged_schedule_sha256: Sha256

    # WorFBench native evaluation.
    worf_protocol_sha256: Sha256
    worf_data_sha256: Sha256
    worf_adapter_sha256: Sha256
    worf_prompt_sha256: Sha256
    worf_evaluator_sha256: Sha256
    worf_schedule_sha256: Sha256

    # tau2 native interactive evaluation.
    tau2_protocol_sha256: Sha256
    tau2_repository_sha256: Sha256
    tau2_task_roster_sha256: Sha256
    tau2_judge_task_roster_sha256: Sha256
    tau2_schedule_sha256: Sha256
    tau2_agent_prompt_sha256: Sha256
    tau2_evaluator_sha256: Sha256

    # Cross-suite inference, runtime, and spend identities.
    public_analysis_code_sha256: Sha256
    custom_failure_policy_sha256: Sha256
    paged_failure_policy_sha256: Sha256
    worf_failure_policy_sha256: Sha256
    tau2_failure_policy_sha256: Sha256
    public_suite_receipt_sha256: Sha256
    primary_backbone_identity_sha256: Sha256
    custom_primary_inference_identity_sha256: Sha256
    paged_primary_inference_identity_sha256: Sha256
    worf_primary_inference_identity_sha256: Sha256
    tau2_primary_inference_identity_sha256: Sha256
    secondary_model_decision_sha256: Sha256
    runtime_image_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    cross_suite_spend_manifest_sha256: Sha256
    statistical_simulation_receipt_sha256: Sha256
    public_floor_evidence_receipt_sha256: Sha256

    # Route canaries are paid but excluded; all three precede this final lock.
    canary_authorization_sha256: Sha256
    together_agent_canary_receipt_sha256: Sha256
    openai_user_canary_receipt_sha256: Sha256
    openai_judge_canary_receipt_sha256: Sha256

    all_locked_rows_required: Literal[True]
    failure_policy: Literal["intention_to_treat_worst_score_plus_complete_case_sensitivity"]
    human_experts_required: Literal[False]
    post_lock_mutation_policy: Literal["new_protocol_version_required"]
    lock_sha256: Sha256

    @model_validator(mode="after")
    def validate_lock(self) -> PublicationStudyLockV3:
        if self.locked_at.tzinfo is None:
            raise ValueError("publication study lock timestamp must include a timezone")
        expected = digest_json(self.model_dump(mode="json", exclude={"lock_sha256"}))
        if self.lock_sha256 != expected:
            raise ValueError("publication v3 study lock hash is stale")
        return self
