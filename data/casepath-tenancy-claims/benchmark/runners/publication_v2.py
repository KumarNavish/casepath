"""Admission and group-aware statistics for publication protocol v2."""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from statistics import fmean
from typing import Literal

from adapters.private_candidate_corpus import VerifiedCorpus
from contracts.publication_v2 import (
    AutonomousOutcomeBundleV2,
    CaseFamilyBindingV2,
    CompilerReceiptV2,
    ConditionV2,
    CustomAbsoluteFloorResultV2,
    DeletionEstimateV2,
    HypothesisSpecV2,
    LanguageEstimateV2,
    LeakageAuditReceiptV2,
    LockedCohortV2,
    ModelInputBundleReceiptV2,
    OracleAuditReceiptV2,
    PublicationAnalysisReceiptV2,
    PublicationEstimateV2,
    PublicationProtocolV2,
    PublicationStudyLockV2,
    PublicBenchmarkAuditReceiptV2,
    PublicBenchmarkRunManifestV2,
    PublicBenchmarkSuiteReceiptV2,
    PublicFloorEvidenceReceiptV2,
    PublicSuiteAcceptanceReceiptV2,
    SensitivitySummaryV2,
    StatisticalSimulationAcceptanceReceiptV2,
)
from manifests.digests import digest_json


@dataclass(frozen=True)
class AdmissionReport:
    reasons: tuple[str, ...]

    @property
    def eligible(self) -> bool:
        return not self.reasons


def protocol_digest(protocol: PublicationProtocolV2) -> str:
    return digest_json(protocol.model_dump(mode="json"))


def absolute_usefulness_policy_digest(protocol: PublicationProtocolV2) -> str:
    return digest_json(protocol.absolute_usefulness.model_dump(mode="json"))


def cohort_digest(cohort: LockedCohortV2) -> str:
    return cohort.cohort_sha256


def study_lock_digest(lock: PublicationStudyLockV2) -> str:
    return digest_json(lock.model_dump(mode="json"))


def public_run_manifest_digest(manifest: PublicBenchmarkRunManifestV2) -> str:
    return digest_json(manifest.model_dump(mode="json"))


def outcome_bundle_digest(bundle: AutonomousOutcomeBundleV2) -> str:
    return digest_json(bundle.model_dump(mode="json"))


def build_locked_cohort(
    corpus: VerifiedCorpus,
    protocol: PublicationProtocolV2,
) -> LockedCohortV2:
    """Bind all 150 authenticated rows to their hidden family metadata."""

    expected = protocol.corpus
    if corpus.manifest_file_sha256 != expected.source_manifest_file_sha256:
        raise ValueError("source manifest file differs from publication protocol v2")
    if corpus.manifest.corpus_sha256 != expected.source_corpus_sha256:
        raise ValueError("source corpus differs from publication protocol v2")
    cases = tuple(
        CaseFamilyBindingV2(
            case_id=row.entry.claim_id,
            domain=row.entry.subtype,
            language=row.entry.language,
            near_duplicate_group_id=row.process_graph["near_duplicate_group_id"],
            scenario_template_id=row.process_graph["scenario_template_id"],
            row_receipt_sha256=row.receipt.row_receipt_sha256,
            role="evaluation",
        )
        for row in corpus.rows
    )
    roster = [
        {
            "case_id": case.case_id,
            "domain": case.domain,
            "language": case.language,
            "near_duplicate_group_id": case.near_duplicate_group_id,
            "scenario_template_id": case.scenario_template_id,
            "row_receipt_sha256": case.row_receipt_sha256,
        }
        for case in cases
    ]
    family_rows = sorted(
        {(case.domain, case.near_duplicate_group_id, case.scenario_template_id) for case in cases}
    )
    families = [
        {
            "domain": domain,
            "near_duplicate_group_id": group_id,
            "scenario_template_id": scenario_id,
        }
        for domain, group_id, scenario_id in family_rows
    ]
    evaluation_family_ids = sorted({case.near_duplicate_group_id for case in cases})
    payload = {
        "cohort_version": "casepath.publication-cohort/2.0.0",
        "cohort_id": "casepath-publication-v2-final-2-all-150",
        "source_manifest_file_sha256": corpus.manifest_file_sha256,
        "source_corpus_sha256": corpus.manifest.corpus_sha256,
        "cases": [case.model_dump(mode="json") for case in cases],
        "prompt_development_family_ids": [],
        "evaluation_family_ids": evaluation_family_ids,
        "case_roster_sha256": digest_json(roster),
        "family_roster_sha256": digest_json(families),
    }
    payload["cohort_sha256"] = digest_json(payload)
    cohort = LockedCohortV2.model_validate(payload)
    if cohort.case_roster_sha256 != expected.case_roster_sha256:
        raise ValueError("authenticated 150-case roster differs from publication protocol v2")
    if cohort.family_roster_sha256 != expected.family_roster_sha256:
        raise ValueError("authenticated 28-family roster differs from publication protocol v2")
    return cohort


def audit_study_lock(
    *,
    lock: PublicationStudyLockV2,
    protocol: PublicationProtocolV2,
    cohort: LockedCohortV2,
    compiler_receipt: CompilerReceiptV2,
    oracle_audit: OracleAuditReceiptV2,
    leakage_audit: LeakageAuditReceiptV2,
    public_suite: PublicBenchmarkSuiteReceiptV2,
    statistical_simulation: StatisticalSimulationAcceptanceReceiptV2,
    public_floor_evidence: PublicFloorEvidenceReceiptV2,
    model_input_bundle: ModelInputBundleReceiptV2,
    analysis_code_sha256: str,
    prompt_template_sha256: str,
    autonomous_runtime_schedule_sha256: str,
    evaluator_bundle_sha256: str,
    model_revision_sha256: str,
    budget_spec_sha256: str,
    runtime_image_digest: str,
) -> AdmissionReport:
    reasons: list[str] = []

    def require(actual: object, expected: object, reason: str) -> None:
        if actual != expected:
            reasons.append(reason)

    require(lock.protocol_sha256, protocol_digest(protocol), "lock does not bind protocol v2")
    require(lock.cohort_sha256, cohort.cohort_sha256, "lock does not bind the 150-case cohort")
    require(
        lock.source_manifest_file_sha256,
        protocol.corpus.source_manifest_file_sha256,
        "lock does not bind the v2-final-2 manifest file",
    )
    require(
        lock.source_corpus_sha256,
        protocol.corpus.source_corpus_sha256,
        "lock does not bind the v2-final-2 semantic corpus",
    )
    require(lock.analysis_code_sha256, analysis_code_sha256, "lock does not bind analysis code")
    require(
        lock.absolute_usefulness_policy_sha256,
        absolute_usefulness_policy_digest(protocol),
        "lock does not bind the absolute-usefulness policy",
    )
    require(
        lock.prompt_template_sha256,
        prompt_template_sha256,
        "lock does not bind the prompt template",
    )
    require(
        lock.model_input_bundle_sha256,
        model_input_bundle.bundle_sha256,
        "lock does not bind the model-input bundle",
    )
    require(
        model_input_bundle.prompt_template_sha256,
        lock.prompt_template_sha256,
        "model-input bundle contains another prompt template",
    )
    require(
        lock.autonomous_runtime_schedule_sha256,
        autonomous_runtime_schedule_sha256,
        "lock does not bind the autonomous runtime schedule",
    )
    require(
        lock.evaluator_bundle_sha256,
        evaluator_bundle_sha256,
        "lock does not bind evaluators",
    )
    require(lock.model_revision_sha256, model_revision_sha256, "lock does not bind model revision")
    require(lock.budget_spec_sha256, budget_spec_sha256, "lock does not bind matched budgets")
    require(lock.runtime_image_digest, runtime_image_digest, "lock does not bind runtime image")
    require(
        lock.compiler_receipt_sha256,
        compiler_receipt.receipt_sha256,
        "lock does not bind compiler receipt",
    )
    require(
        lock.oracle_audit_receipt_sha256,
        oracle_audit.receipt_sha256,
        "lock does not bind oracle-audit receipt",
    )
    require(
        lock.leakage_audit_receipt_sha256,
        leakage_audit.receipt_sha256,
        "lock does not bind leakage-audit receipt",
    )
    require(
        lock.public_benchmark_suite_receipt_sha256,
        public_suite.receipt_sha256,
        "lock does not bind public-benchmark-suite receipt",
    )
    require(
        lock.statistical_simulation_receipt_sha256,
        statistical_simulation.receipt_sha256,
        "lock does not bind statistical-simulation receipt",
    )
    require(
        lock.public_floor_evidence_receipt_sha256,
        public_floor_evidence.receipt_sha256,
        "lock does not bind public-floor evidence",
    )
    if any(
        gate.baseline_extraction_receipt_sha256 != public_floor_evidence.receipt_sha256
        for gate in protocol.absolute_usefulness.public_gates
    ):
        reasons.append("protocol public gates do not bind the supplied floor evidence")
    require(
        statistical_simulation.protocol_sha256,
        lock.protocol_sha256,
        "statistical simulation covers another protocol",
    )
    require(
        compiler_receipt.source_manifest_file_sha256,
        lock.source_manifest_file_sha256,
        "compiler used another source manifest",
    )
    require(
        compiler_receipt.source_corpus_sha256,
        lock.source_corpus_sha256,
        "compiler used another semantic corpus",
    )
    require(compiler_receipt.cohort_sha256, cohort.cohort_sha256, "compiler used another cohort")
    require(
        oracle_audit.compiler_receipt_sha256,
        compiler_receipt.receipt_sha256,
        "oracle audit covers another compiler receipt",
    )
    require(
        leakage_audit.cohort_sha256, cohort.cohort_sha256, "leakage audit covers another cohort"
    )
    require(
        leakage_audit.prompt_template_sha256,
        lock.prompt_template_sha256,
        "leakage audit covers another prompt template",
    )
    require(
        leakage_audit.model_input_bundle_sha256,
        lock.model_input_bundle_sha256,
        "leakage audit covers another model-input bundle",
    )
    require(
        leakage_audit.evaluation_family_ids,
        cohort.evaluation_family_ids,
        "leakage audit does not cover all 28 evaluation families",
    )
    return AdmissionReport(tuple(reasons))


def admit_public_benchmark_run(
    suite: PublicBenchmarkSuiteReceiptV2,
    audit: PublicBenchmarkAuditReceiptV2,
    run: PublicBenchmarkRunManifestV2,
) -> AdmissionReport:
    """Admit scores only after exact native-evaluator and provenance binding."""

    reasons: list[str] = []
    candidate = next(
        (item for item in suite.candidates if item.benchmark_id == run.benchmark_id), None
    )
    if candidate is None:
        return AdmissionReport(("run benchmark is absent from the declarative suite",))
    expected: dict[str, object] = {
        "benchmark_id": audit.benchmark_id,
        "audit_receipt_sha256": audit.receipt_sha256,
        "provenance_manifest_sha256": audit.provenance_manifest_sha256,
        "code_revision": audit.code_revision,
        "native_evaluator": audit.native_evaluator,
        "native_evaluator_sha256": audit.native_evaluator_sha256,
        "split_id": audit.split_id,
        "split_sha256": audit.split_sha256,
        "data_sha256": audit.data_sha256,
        "license_sha256": audit.license_sha256,
        "adapter_sha256": audit.adapter_sha256,
        "native_case_count": audit.expected_native_case_count,
        "trials_per_case": audit.expected_trials_per_case,
    }
    for field, value in expected.items():
        if getattr(run, field) != value:
            reasons.append(f"public run does not bind audited {field}")
    if candidate.code_revision != run.code_revision:
        reasons.append("public run code revision differs from the declared candidate")
    if candidate.native_evaluator != run.native_evaluator:
        reasons.append("public run does not use the declared benchmark-native evaluator")
    if run.benchmark_id == "worfbench-iclr2025-test" and (
        "released_code_worfeval" not in run.native_endpoint_ids
    ):
        reasons.append("WorFBench run omits released-code WorFEval")
    if run.benchmark_id.startswith("tau2-bench") and (
        "tau2_task_reward_basis" not in run.native_endpoint_ids
    ):
        reasons.append("tau2 run omits its task-selected native reward_basis")
    return AdmissionReport(tuple(reasons))


def admit_public_suite_acceptance(
    *,
    receipt: PublicSuiteAcceptanceReceiptV2,
    protocol: PublicationProtocolV2,
    suite: PublicBenchmarkSuiteReceiptV2,
    worf_run: PublicBenchmarkRunManifestV2,
    tau2_run: PublicBenchmarkRunManifestV2,
    floor_evidence: PublicFloorEvidenceReceiptV2,
    worfbench_paired_acceptance_receipt_sha256: str,
    tau2_core_paired_acceptance_receipt_sha256: str,
) -> AdmissionReport:
    reasons: list[str] = []
    if receipt.protocol_sha256 != protocol_digest(protocol):
        reasons.append("utility receipt does not bind publication protocol v2")
    if receipt.suite_receipt_sha256 != suite.receipt_sha256:
        reasons.append("utility receipt does not bind the public suite")
    expected_gate_digest = digest_json(
        [item.model_dump(mode="json") for item in protocol.absolute_usefulness.public_gates]
    )
    if receipt.absolute_gate_spec_sha256 != expected_gate_digest:
        reasons.append("utility receipt does not bind the public absolute gates")
    if receipt.public_floor_evidence_receipt_sha256 != floor_evidence.receipt_sha256:
        reasons.append("utility receipt does not bind public-floor evidence")
    if (
        receipt.worfbench_paired_acceptance_receipt_sha256
        != worfbench_paired_acceptance_receipt_sha256
    ):
        reasons.append("utility receipt does not bind WorFBench matched-arm acceptance")
    if (
        receipt.tau2_core_paired_acceptance_receipt_sha256
        != tau2_core_paired_acceptance_receipt_sha256
    ):
        reasons.append("utility receipt does not bind tau2 matched-arm acceptance")
    if worf_run.benchmark_id != "worfbench-iclr2025-test":
        reasons.append("utility receipt lacks the required WorFBench run")
    if tau2_run.benchmark_id != "tau2-bench-v1.0.1-core":
        reasons.append("utility receipt lacks the required tau2 core run")
    if receipt.worfbench_run_manifest_sha256 != public_run_manifest_digest(worf_run):
        reasons.append("utility receipt does not bind the WorFBench run")
    if receipt.tau2_core_run_manifest_sha256 != public_run_manifest_digest(tau2_run):
        reasons.append("utility receipt does not bind the tau2 core run")
    if "released_code_worfeval" not in worf_run.native_endpoint_ids:
        reasons.append("utility receipt lacks released-code WorFEval")
    if "tau2_task_reward_basis" not in tau2_run.native_endpoint_ids:
        reasons.append("utility receipt lacks tau2 terminal task success")
    gate_specs = {item.benchmark_id: item for item in protocol.absolute_usefulness.public_gates}
    gate_results = {item.benchmark_id: item for item in receipt.absolute_gate_results}
    for benchmark_id in ("worfbench-iclr2025-test", "tau2-bench-v1.0.1-core"):
        spec = gate_specs[benchmark_id]
        result = gate_results[benchmark_id]
        if spec.status != "pinned":
            reasons.append(
                f"{benchmark_id} absolute floor and cost ceilings await audited baseline extraction"
            )
            continue
        if spec.baseline_extraction_receipt_sha256 != floor_evidence.receipt_sha256:
            reasons.append(f"{benchmark_id} gate does not bind public-floor evidence")
            continue
        if (
            result.native_endpoint_id != spec.native_endpoint_id
            or result.minimum_native_score != spec.minimum_native_score
            or result.cost_ceiling != spec.cost_ceiling
        ):
            reasons.append(f"{benchmark_id} result does not use the pinned absolute gates")
        elif not result.passed:
            reasons.append(f"{benchmark_id} fails its native floor or cost ceilings")
    if not receipt.full_usefulness_public_guardrail_passed:
        reasons.append("public absolute usefulness guardrails did not all pass")
    return AdmissionReport(tuple(reasons))


def _cluster_values(
    case_benefits: Mapping[str, float],
    cohort: LockedCohortV2,
    *,
    language: str | None = None,
    excluded_family: str | None = None,
    excluded_domain: str | None = None,
    included_domain: str | None = None,
) -> dict[str, dict[str, float]]:
    by_cluster: dict[tuple[str, str], list[float]] = defaultdict(list)
    for case in cohort.cases:
        if language is not None and case.language != language:
            continue
        if excluded_family is not None and case.near_duplicate_group_id == excluded_family:
            continue
        if excluded_domain is not None and case.domain == excluded_domain:
            continue
        if included_domain is not None and case.domain != included_domain:
            continue
        try:
            value = case_benefits[case.case_id]
        except KeyError as exc:
            raise ValueError(f"missing paired benefit for case {case.case_id}") from exc
        by_cluster[(case.domain, case.near_duplicate_group_id)].append(value)
    if set(case_benefits) != {case.case_id for case in cohort.cases}:
        raise ValueError("paired benefits contain cases outside the locked cohort")
    strata: dict[str, dict[str, float]] = defaultdict(dict)
    for (domain, cluster_id), values in by_cluster.items():
        strata[domain][cluster_id] = fmean(values)
    expected_domains = 1 if included_domain is not None else 2 if excluded_domain is not None else 3
    if len(strata) != expected_domains or any(len(values) < 2 for values in strata.values()):
        raise ValueError("each retained domain requires at least two family clusters")
    if (
        language is None
        and excluded_family is None
        and excluded_domain is None
        and included_domain is None
        and {domain: len(values) for domain, values in strata.items()}
        != {
            "defect_mold_heating": 10,
            "lease_termination_dispute": 8,
            "rent_increase_dispute": 10,
        }
    ):
        raise ValueError("paired benefits do not form the locked 10/8/10 family strata")
    return dict(strata)


def _macro_from_clusters(strata: Mapping[str, Mapping[str, float]]) -> float:
    return fmean(fmean(clusters.values()) for _, clusters in sorted(strata.items()))


def stratified_family_macro(case_benefits: Mapping[str, float], cohort: LockedCohortV2) -> float:
    """Equal weight to cases within family, families within domain, and domains."""

    return _macro_from_clusters(_cluster_values(case_benefits, cohort))


def stratified_family_macro_subset(
    case_benefits: Mapping[str, float],
    cohort: LockedCohortV2,
    *,
    excluded_family: str | None = None,
    excluded_domain: str | None = None,
) -> float:
    return _macro_from_clusters(
        _cluster_values(
            case_benefits,
            cohort,
            excluded_family=excluded_family,
            excluded_domain=excluded_domain,
        )
    )


def stratified_family_jackknife(
    case_benefits: Mapping[str, float], cohort: LockedCohortV2
) -> tuple[float, ...]:
    strata = _cluster_values(case_benefits, cohort)
    values: list[float] = []
    for domain, clusters in sorted(strata.items()):
        for cluster_id in sorted(clusters):
            reduced = {
                item_domain: {
                    item_cluster: value
                    for item_cluster, value in item_clusters.items()
                    if not (item_domain == domain and item_cluster == cluster_id)
                }
                for item_domain, item_clusters in strata.items()
            }
            values.append(_macro_from_clusters(reduced))
    return tuple(values)


def _beta_continued_fraction(a: float, b: float, x: float) -> float:
    tiny = 3e-14
    qab = a + b
    qap = a + 1.0
    qam = a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < tiny:
        d = tiny
    d = 1.0 / d
    result = d
    for index in range(1, 201):
        doubled = 2 * index
        coefficient = index * (b - index) * x / ((qam + doubled) * (a + doubled))
        d = 1.0 + coefficient * d
        d = tiny if abs(d) < tiny else d
        c = 1.0 + coefficient / c
        c = tiny if abs(c) < tiny else c
        d = 1.0 / d
        result *= d * c
        coefficient = -(a + index) * (qab + index) * x / ((a + doubled) * (qap + doubled))
        d = 1.0 + coefficient * d
        d = tiny if abs(d) < tiny else d
        c = 1.0 + coefficient / c
        c = tiny if abs(c) < tiny else c
        d = 1.0 / d
        delta = d * c
        result *= delta
        if abs(delta - 1.0) < 3e-12:
            break
    return result


def _regularized_beta(a: float, b: float, x: float) -> float:
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    front = math.exp(
        math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log1p(-x)
    )
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _beta_continued_fraction(a, b, x) / a
    return 1.0 - front * _beta_continued_fraction(b, a, 1.0 - x) / b


def student_t_cdf(value: float, degrees_of_freedom: float) -> float:
    if degrees_of_freedom <= 0.0 or not math.isfinite(degrees_of_freedom):
        raise ValueError("finite positive degrees of freedom are required")
    x = degrees_of_freedom / (degrees_of_freedom + value * value)
    tail = 0.5 * _regularized_beta(degrees_of_freedom / 2.0, 0.5, x)
    return 1.0 - tail if value >= 0.0 else tail


def student_t_quantile(probability: float, degrees_of_freedom: float) -> float:
    if not 0.0 < probability < 1.0:
        raise ValueError("Student-t probability must lie strictly inside (0, 1)")
    if probability < 0.5:
        return -student_t_quantile(1.0 - probability, degrees_of_freedom)
    lower = 0.0
    upper = 1.0
    while student_t_cdf(upper, degrees_of_freedom) < probability:
        upper *= 2.0
    for _ in range(80):
        midpoint = (lower + upper) / 2.0
        if student_t_cdf(midpoint, degrees_of_freedom) < probability:
            lower = midpoint
        else:
            upper = midpoint
    return (lower + upper) / 2.0


@dataclass(frozen=True)
class ClusterTResult:
    estimate: float
    standard_error: float
    degrees_of_freedom: float
    confidence_lower: float
    confidence_upper: float
    analyzed_cases: int
    analyzed_families: int
    analyzed_domains: int


def stratified_family_cluster_moments(
    case_benefits: Mapping[str, float],
    cohort: LockedCohortV2,
    *,
    language: str | None = None,
    excluded_family: str | None = None,
    excluded_domain: str | None = None,
    included_domain: str | None = None,
) -> tuple[float, float, float, int, int, int]:
    """Point estimate, cluster SE, Satterthwaite df, and retained counts."""

    strata = _cluster_values(
        case_benefits,
        cohort,
        language=language,
        excluded_family=excluded_family,
        excluded_domain=excluded_domain,
        included_domain=included_domain,
    )
    observed = _macro_from_clusters(strata)
    domain_count = len(strata)
    components: list[tuple[float, int]] = []
    for clusters in strata.values():
        values = tuple(clusters.values())
        mean = fmean(values)
        variance = sum((value - mean) ** 2 for value in values) / (len(values) - 1)
        components.append((variance / len(values) / domain_count**2, len(values)))
    total_variance = sum(value for value, _ in components)
    if total_variance == 0.0:
        degrees_of_freedom = float(sum(count - 1 for _, count in components))
    else:
        denominator = sum(value * value / (count - 1) for value, count in components)
        degrees_of_freedom = total_variance * total_variance / denominator
    included_cases = sum(
        language is None or case.language == language
        for case in cohort.cases
        if (excluded_family is None or case.near_duplicate_group_id != excluded_family)
        and (excluded_domain is None or case.domain != excluded_domain)
        and (included_domain is None or case.domain == included_domain)
    )
    return (
        observed,
        math.sqrt(total_variance),
        degrees_of_freedom,
        included_cases,
        sum(len(clusters) for clusters in strata.values()),
        domain_count,
    )


def stratified_family_cluster_t(
    case_benefits: Mapping[str, float],
    cohort: LockedCohortV2,
    *,
    confidence_level: float,
    language: str | None = None,
    excluded_family: str | None = None,
    excluded_domain: str | None = None,
    included_domain: str | None = None,
) -> ClusterTResult:
    """Small-sample cluster-t interval for the equal-domain macro estimand."""

    estimate, standard_error, degrees_of_freedom, cases, families, domains = (
        stratified_family_cluster_moments(
            case_benefits,
            cohort,
            language=language,
            excluded_family=excluded_family,
            excluded_domain=excluded_domain,
            included_domain=included_domain,
        )
    )
    if standard_error == 0.0:
        lower = upper = estimate
    else:
        critical = student_t_quantile(0.5 + confidence_level / 2.0, degrees_of_freedom)
        half_width = critical * standard_error
        lower = estimate - half_width
        upper = estimate + half_width
    return ClusterTResult(
        estimate=estimate,
        standard_error=standard_error,
        degrees_of_freedom=degrees_of_freedom,
        confidence_lower=lower,
        confidence_upper=upper,
        analyzed_cases=cases,
        analyzed_families=families,
        analyzed_domains=domains,
    )


def _hypothesis_p_value(hypothesis: HypothesisSpecV2, result: ClusterTResult) -> float:
    def one_sided(boundary: float, alternative: Literal["greater", "less"]) -> float:
        if result.standard_error == 0.0:
            if alternative == "greater":
                return 0.0 if result.estimate > boundary else 1.0
            return 0.0 if result.estimate < boundary else 1.0
        statistic = (result.estimate - boundary) / result.standard_error
        cumulative = student_t_cdf(statistic, result.degrees_of_freedom)
        return 1.0 - cumulative if alternative == "greater" else cumulative

    if hypothesis.decision_rule == "superiority":
        return one_sided(hypothesis.margin, "greater")
    if hypothesis.decision_rule == "noninferiority":
        return one_sided(-hypothesis.margin, "greater")
    lower = one_sided(-hypothesis.margin, "greater")
    upper = one_sided(hypothesis.margin, "less")
    return max(lower, upper)


def _margin_passed(hypothesis: HypothesisSpecV2, lower: float, upper: float) -> bool:
    if hypothesis.decision_rule == "superiority":
        return lower > hypothesis.margin
    if hypothesis.decision_rule == "noninferiority":
        return lower > -hypothesis.margin
    return lower > -hypothesis.margin and upper < hypothesis.margin


def _holm_adjusted(raw: Mapping[str, float]) -> dict[str, float]:
    ordered = sorted(raw.items(), key=lambda item: (item[1], item[0]))
    count = len(ordered)
    running = 0.0
    adjusted: dict[str, float] = {}
    for index, (hypothesis_id, p_value) in enumerate(ordered):
        running = max(running, min(1.0, (count - index) * p_value))
        adjusted[hypothesis_id] = running
    return adjusted


@dataclass(frozen=True)
class _UnadjustedEstimate:
    hypothesis: HypothesisSpecV2
    estimate: float
    lower: float
    upper: float
    raw_p: float
    margin_passed: bool
    treatment_missing: int
    control_missing: int
    treatment_failures: int
    control_failures: int


def analyze_autonomous_outcomes(
    *,
    protocol: PublicationProtocolV2,
    lock: PublicationStudyLockV2,
    cohort: LockedCohortV2,
    bundle: AutonomousOutcomeBundleV2,
) -> PublicationAnalysisReceiptV2:
    if lock.protocol_sha256 != protocol_digest(protocol):
        raise ValueError("study lock does not bind publication protocol v2")
    if lock.cohort_sha256 != cohort.cohort_sha256:
        raise ValueError("study lock does not bind the supplied cohort")
    if bundle.study_lock_sha256 != study_lock_digest(lock):
        raise ValueError("outcomes do not bind the admitted study lock")
    if bundle.cohort_sha256 != cohort.cohort_sha256:
        raise ValueError("outcomes do not bind the locked cohort")

    endpoints = {endpoint.endpoint_id: endpoint for endpoint in protocol.endpoints}
    indexed: dict[tuple[str, ConditionV2, str], tuple[float, str]] = {}
    for outcome in bundle.outcomes:
        key = (outcome.case_id, outcome.condition, outcome.endpoint_id)
        if key in indexed:
            raise ValueError(f"duplicate autonomous outcome: {key}")
        endpoint = endpoints[outcome.endpoint_id]
        if outcome.status == "observed":
            assert outcome.value is not None
            score = outcome.value
        elif outcome.status == "missing":
            score = endpoint.missing_score
        else:
            score = endpoint.system_failure_score
        indexed[key] = (score, outcome.status)
    expected_grid: set[tuple[str, ConditionV2, str]] = {
        (case.case_id, condition, endpoint.endpoint_id)
        for case in cohort.cases
        for condition in protocol.conditions
        for endpoint in protocol.endpoints
    }
    indexed_keys: set[tuple[str, ConditionV2, str]] = set(indexed)
    if indexed_keys != expected_grid:
        missing = len(expected_grid - indexed_keys)
        extra = len(indexed_keys - expected_grid)
        raise ValueError(
            f"outcomes must form the full 150x5x5 grid (missing={missing}, extra={extra})"
        )

    unadjusted: dict[str, tuple[str, _UnadjustedEstimate]] = {}
    benefits_by_hypothesis: dict[str, dict[str, float]] = {}
    for family in protocol.multiplicity_families:
        for hypothesis in family.hypotheses:
            endpoint = endpoints[hypothesis.endpoint_id]
            treatment_rows = {
                case.case_id: indexed[(case.case_id, hypothesis.treatment, hypothesis.endpoint_id)]
                for case in cohort.cases
            }
            control_rows = {
                case.case_id: indexed[(case.case_id, hypothesis.control, hypothesis.endpoint_id)]
                for case in cohort.cases
            }
            sign = 1.0 if endpoint.direction == "higher" else -1.0
            benefits = {
                case.case_id: sign
                * (treatment_rows[case.case_id][0] - control_rows[case.case_id][0])
                for case in cohort.cases
            }
            result = stratified_family_cluster_t(
                benefits,
                cohort,
                confidence_level=protocol.estimand.confidence_level,
            )
            raw_p = _hypothesis_p_value(hypothesis, result)
            benefits_by_hypothesis[hypothesis.hypothesis_id] = benefits
            unadjusted[hypothesis.hypothesis_id] = (
                family.family_id,
                _UnadjustedEstimate(
                    hypothesis=hypothesis,
                    estimate=result.estimate,
                    lower=result.confidence_lower,
                    upper=result.confidence_upper,
                    raw_p=raw_p,
                    margin_passed=_margin_passed(
                        hypothesis, result.confidence_lower, result.confidence_upper
                    ),
                    treatment_missing=sum(
                        status == "missing" for _, status in treatment_rows.values()
                    ),
                    control_missing=sum(status == "missing" for _, status in control_rows.values()),
                    treatment_failures=sum(
                        status == "system_failure" for _, status in treatment_rows.values()
                    ),
                    control_failures=sum(
                        status == "system_failure" for _, status in control_rows.values()
                    ),
                ),
            )
    language_secondary: list[LanguageEstimateV2] = []
    sensitivities: list[SensitivitySummaryV2] = []
    for hypothesis_id, benefits in benefits_by_hypothesis.items():
        full_estimate = unadjusted[hypothesis_id][1].estimate
        for language in ("de-CH", "en"):
            result = stratified_family_cluster_t(
                benefits,
                cohort,
                confidence_level=protocol.estimand.confidence_level,
                language=language,
            )
            language_secondary.append(
                LanguageEstimateV2(
                    hypothesis_id=hypothesis_id,
                    language=language,
                    benefit_estimate=result.estimate,
                    confidence_lower=result.confidence_lower,
                    confidence_upper=result.confidence_upper,
                    analyzed_cases=75,
                    analyzed_families=result.analyzed_families,
                    analyzed_domains=3,
                )
            )
        family_deletions = tuple(
            DeletionEstimateV2(
                excluded_id=family_id,
                benefit_estimate=stratified_family_macro_subset(
                    benefits,
                    cohort,
                    excluded_family=family_id,
                ),
            )
            for family_id in cohort.evaluation_family_ids
        )
        domain_deletions = tuple(
            DeletionEstimateV2(
                excluded_id=domain,
                benefit_estimate=stratified_family_macro_subset(
                    benefits,
                    cohort,
                    excluded_domain=domain,
                ),
            )
            for domain in (
                "defect_mold_heating",
                "lease_termination_dispute",
                "rent_increase_dispute",
            )
        )
        sensitivities.append(
            SensitivitySummaryV2(
                hypothesis_id=hypothesis_id,
                full_benefit_estimate=full_estimate,
                leave_one_family=family_deletions,
                leave_one_domain=domain_deletions,
                maximum_absolute_family_shift=max(
                    abs(item.benefit_estimate - full_estimate) for item in family_deletions
                ),
                maximum_absolute_domain_shift=max(
                    abs(item.benefit_estimate - full_estimate) for item in domain_deletions
                ),
            )
        )

    estimates: list[PublicationEstimateV2] = []
    for family in protocol.multiplicity_families:
        raw = {
            item.hypothesis_id: unadjusted[item.hypothesis_id][1].raw_p
            for item in family.hypotheses
        }
        adjusted = _holm_adjusted(raw)
        for hypothesis in family.hypotheses:
            value = unadjusted[hypothesis.hypothesis_id][1]
            multiplicity_passed = adjusted[hypothesis.hypothesis_id] <= family.familywise_alpha
            estimates.append(
                PublicationEstimateV2(
                    hypothesis_id=hypothesis.hypothesis_id,
                    family_id=family.family_id,
                    endpoint_id=hypothesis.endpoint_id,
                    treatment=hypothesis.treatment,
                    control=hypothesis.control,
                    decision_rule=hypothesis.decision_rule,
                    margin=hypothesis.margin,
                    benefit_estimate=value.estimate,
                    confidence_lower=value.lower,
                    confidence_upper=value.upper,
                    raw_p_value=value.raw_p,
                    adjusted_p_value=adjusted[hypothesis.hypothesis_id],
                    margin_passed=value.margin_passed,
                    multiplicity_passed=multiplicity_passed,
                    passed=value.margin_passed and multiplicity_passed,
                    analyzed_cases=150,
                    analyzed_families=28,
                    analyzed_domains=3,
                    treatment_missing=value.treatment_missing,
                    control_missing=value.control_missing,
                    treatment_failures=value.treatment_failures,
                    control_failures=value.control_failures,
                )
            )
    headline_ids = tuple(
        item.hypothesis_id
        for family in protocol.multiplicity_families
        if family.family_id == "custom_headline"
        for item in family.hypotheses
    )
    estimate_map = {estimate.hypothesis_id: estimate for estimate in estimates}
    absolute_floor_results: list[CustomAbsoluteFloorResultV2] = []
    for floor in protocol.absolute_usefulness.custom_floors:
        scores = {
            case.case_id: indexed[(case.case_id, "B7", floor.endpoint_id)][0]
            for case in cohort.cases
        }
        for scope in (
            "pooled",
            "defect_mold_heating",
            "lease_termination_dispute",
            "rent_increase_dispute",
        ):
            result = stratified_family_cluster_t(
                scores,
                cohort,
                confidence_level=protocol.estimand.confidence_level,
                included_domain=None if scope == "pooled" else scope,
            )
            passed = (
                result.confidence_lower >= floor.threshold
                if floor.direction == "higher"
                else result.confidence_upper <= floor.threshold
            )
            absolute_floor_results.append(
                CustomAbsoluteFloorResultV2(
                    condition="B7",
                    endpoint_id=floor.endpoint_id,
                    scope=scope,
                    direction=floor.direction,
                    threshold=floor.threshold,
                    estimate=result.estimate,
                    confidence_lower=result.confidence_lower,
                    confidence_upper=result.confidence_upper,
                    passed=passed,
                    analyzed_cases=result.analyzed_cases,
                    analyzed_families=result.analyzed_families,
                    analyzed_domains=result.analyzed_domains,
                )
            )
    relative_mechanism_success = all(estimate_map[item].passed for item in headline_ids)
    custom_absolute_quality_success = all(item.passed for item in absolute_floor_results)
    payload = {
        "receipt_version": "casepath.publication-analysis/2.1.0",
        "protocol_sha256": protocol_digest(protocol),
        "study_lock_sha256": study_lock_digest(lock),
        "cohort_sha256": cohort.cohort_sha256,
        "outcome_bundle_sha256": outcome_bundle_digest(bundle),
        "estimates": [estimate.model_dump(mode="json") for estimate in estimates],
        "language_secondary": [estimate.model_dump(mode="json") for estimate in language_secondary],
        "sensitivity": [item.model_dump(mode="json") for item in sensitivities],
        "custom_absolute_floor_results": [
            item.model_dump(mode="json") for item in absolute_floor_results
        ],
        "headline_hypothesis_ids": list(headline_ids),
        "relative_mechanism_claim_success": relative_mechanism_success,
        "custom_absolute_quality_success": custom_absolute_quality_success,
        "headline_success": relative_mechanism_success and custom_absolute_quality_success,
        "full_usefulness_claim_status": "requires_separate_public_suite_acceptance",
        "human_evidence_used": False,
    }
    payload["receipt_sha256"] = digest_json(payload)
    return PublicationAnalysisReceiptV2.model_validate(payload)


def failure_summary(bundle: AutonomousOutcomeBundleV2) -> dict[str, dict[str, int]]:
    """Report every missing/failure row; never drop them from the analysis."""

    counts: dict[str, Counter[str]] = defaultdict(Counter)
    for outcome in bundle.outcomes:
        counts[outcome.condition][outcome.status] += 1
    return {
        condition: dict(sorted(statuses.items())) for condition, statuses in sorted(counts.items())
    }
