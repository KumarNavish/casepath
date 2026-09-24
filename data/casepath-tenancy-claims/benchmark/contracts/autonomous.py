"""Typed identities for the autonomous synthetic benchmark compilation boundary."""

from __future__ import annotations

from collections import Counter
from typing import Any, Literal

from pydantic import Field, model_validator

from manifests.digests import digest_json

from .schema import AcceptanceContract, StrictModel
from .traceability_v3 import TraceabilityContractV3

Sha256 = str
Subtype = Literal[
    "defect_mold_heating",
    "lease_termination_dispute",
    "rent_increase_dispute",
]
Language = Literal["de-CH", "en"]
WilliamsSequence = Literal["W1", "W2", "W3", "W4"]
CohortRole = Literal["primary", "compiler_canary"]
AutonomousGatePolicyItem = tuple[str, str, Literal[">=", "<=", ">", "<", "=="], float]

# This fingerprint lets the production runner admit the compiled evaluator
# semantics without opening evaluator-vault files. Any gate change requires a
# compiler-version and compilation-hash change.
AUTONOMOUS_FATAL_GATE_POLICY: tuple[AutonomousGatePolicyItem, ...] = (
    ("process-path-exact", "valid_path_rate", ">=", 1.0),
    ("required-nodes-complete", "required_node_recall", ">=", 1.0),
    ("required-edges-complete", "required_edge_recall", ">=", 1.0),
    ("branch-semantics-exact", "branch_predicate_accuracy", ">=", 1.0),
    (
        "evidence-obligations-complete",
        "evidence_obligation_completeness",
        ">=",
        1.0,
    ),
    ("document-states-exact", "document_state_accuracy", ">=", 1.0),
    ("no-unnecessary-documents", "unnecessary_document_rate", "<=", 0.0),
    ("no-forbidden-concepts", "forbidden_concept_violation_rate", "<=", 0.0),
)
AUTONOMOUS_FATAL_GATE_POLICY_SHA256 = digest_json(AUTONOMOUS_FATAL_GATE_POLICY)


class GenericPolicySource(StrictModel):
    source_id: str
    subtype: Subtype
    title: str
    content: str = Field(min_length=1)
    source_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_content_hash(self) -> GenericPolicySource:
        if self.source_sha256 != digest_json(
            {
                "source_id": self.source_id,
                "subtype": self.subtype,
                "title": self.title,
                "content": self.content,
            }
        ):
            raise ValueError("generic policy source has a stale content hash")
        return self


class GenericPolicyBundle(StrictModel):
    contract: Literal["casepath.generic-policy-bundle/1.0.0"]
    sources: tuple[GenericPolicySource, ...] = Field(min_length=3, max_length=3)
    bundle_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_bundle(self) -> GenericPolicyBundle:
        subtypes = [source.subtype for source in self.sources]
        if len(set(subtypes)) != 3:
            raise ValueError("generic policy bundle requires one source per subtype")
        if tuple(subtypes) != tuple(sorted(subtypes)):
            raise ValueError("generic policy sources must be sorted by subtype")
        payload = self.model_dump(mode="json", exclude={"bundle_sha256"})
        if self.bundle_sha256 != digest_json(payload):
            raise ValueError("generic policy bundle has a stale hash")
        return self


class AutonomousBenchmarkSeal(StrictModel):
    contract: Literal["casepath.autonomous-benchmark-seal/1.0.0"]
    source_manifest_name: Literal["corpus-manifest.json"]
    source_contract: Literal["casepath.private-candidate-corpus/2.0.0"]
    source_manifest_file_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    source_corpus_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    source_plan_contract: Literal["casepath.dataset-production-plan/5.0.0"]
    source_plan_file_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    source_plan_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    policy_bundle_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    compiler_version: Literal["casepath.autonomous-benchmark-compiler/1.1.0"]
    ground_truth_kind: Literal["deterministic_generator_hidden_state"]
    human_review_policy: Literal["optional_not_an_admission_gate"]
    source_rows: Literal[150]
    primary_rows: Literal[144]
    compiler_canary_rows: Literal[6]
    primary_rows_per_domain_language_cell: Literal[24]
    compiler_canaries_per_domain_language_cell: Literal[1]
    williams_sequences: tuple[WilliamsSequence, ...] = ("W1", "W2", "W3", "W4")
    primary_rows_per_sequence_per_cell: Literal[6]
    cohort_assignment_algorithm: Literal[
        "sha256(corpus_sha256\\0subtype\\0language\\0claim_id); "
        "lowest key is canary; remaining keys cycle W1,W2,W3,W4"
    ]
    runtime_model_calls: Literal[0]
    seal_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_seal_hash(self) -> AutonomousBenchmarkSeal:
        if self.seal_sha256 != digest_json(self.model_dump(mode="json", exclude={"seal_sha256"})):
            raise ValueError("autonomous benchmark seal has a stale hash")
        return self


class AutonomousModelPacket(StrictModel):
    packet_version: Literal["casepath.autonomous-model-packet/1.0.0"]
    case_id: str
    language: Language
    observable_claim: dict[str, Any]
    observable_claim_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    policy_sources: tuple[GenericPolicySource, ...] = Field(min_length=1, max_length=1)
    policy_bundle_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    source_corpus_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    source_row_receipt_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    packet_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_packet_hashes(self) -> AutonomousModelPacket:
        if self.observable_claim_sha256 != digest_json(self.observable_claim):
            raise ValueError("model packet observable claim hash differs")
        if self.policy_sources[0].subtype not in self.policy_sources[0].source_id:
            raise ValueError("model packet policy source ID is not subtype-bound")
        if self.packet_sha256 != digest_json(
            self.model_dump(mode="json", exclude={"packet_sha256"})
        ):
            raise ValueError("autonomous model packet has a stale hash")
        return self


class AutonomousEvaluatorContract(StrictModel):
    evaluator_contract_version: Literal["casepath.autonomous-evaluator-contract/1.0.0"]
    case_id: str
    ground_truth_kind: Literal["deterministic_generator_hidden_state"]
    acceptance_contract: AcceptanceContract
    expected_claim_category: Subtype
    expected_tenant_law_subcategory: str
    expected_next_action: dict[str, Any]
    expected_current_process_state: dict[str, Any]
    traceability_contract: TraceabilityContractV3 | None = None
    source_file_sha256: dict[str, Sha256]
    source_corpus_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    source_row_receipt_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    evaluator_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_evaluator_contract(self) -> AutonomousEvaluatorContract:
        if self.case_id != self.acceptance_contract.case_id:
            raise ValueError("evaluator wrapper and acceptance contract case IDs differ")
        if (
            self.traceability_contract is not None
            and self.traceability_contract.case_id != self.case_id
        ):
            raise ValueError("traceability and evaluator case IDs differ")
        serialized = self.model_dump(mode="json", exclude={"evaluator_sha256"})
        if self.traceability_contract is None:
            serialized.pop("traceability_contract")
        if self.evaluator_sha256 != digest_json(serialized):
            raise ValueError("autonomous evaluator contract has a stale hash")
        return self


class CompiledCaseEntry(StrictModel):
    claim_id: str
    subtype: Subtype
    language: Language
    cohort_role: CohortRole
    williams_sequence: WilliamsSequence | None
    model_packet_path: str
    model_packet_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    evaluator_contract_path: str
    evaluator_contract_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    source_row_receipt_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_assignment(self) -> CompiledCaseEntry:
        if (self.cohort_role == "primary") != (self.williams_sequence is not None):
            raise ValueError("only primary cases receive a Williams sequence")
        return self


class AutonomousCompilationManifest(StrictModel):
    contract: Literal["casepath.autonomous-benchmark-compilation/1.0.0"]
    compiler_version: Literal["casepath.autonomous-benchmark-compiler/1.1.0"]
    fatal_gate_policy_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    seal_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    source_manifest_file_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    source_corpus_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    source_plan_file_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    source_plan_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    policy_bundle_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    ground_truth_kind: Literal["deterministic_generator_hidden_state"]
    human_review_used: Literal[False]
    runtime_model_calls: Literal[0]
    cases: tuple[CompiledCaseEntry, ...] = Field(min_length=150, max_length=150)
    model_file_set_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    evaluator_file_set_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    compilation_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_compilation(self) -> AutonomousCompilationManifest:
        if self.fatal_gate_policy_sha256 != AUTONOMOUS_FATAL_GATE_POLICY_SHA256:
            raise ValueError("compiled fatal-gate policy differs from compiler 1.1")
        claim_ids = [case.claim_id for case in self.cases]
        if len(set(claim_ids)) != 150:
            raise ValueError("compiled case IDs must be unique")
        role_counts = Counter(case.cohort_role for case in self.cases)
        if role_counts != Counter({"primary": 144, "compiler_canary": 6}):
            raise ValueError("compiled cohort must contain 144 primary and six canary cases")
        cells = Counter((case.subtype, case.language) for case in self.cases)
        if set(cells.values()) != {25} or len(cells) != 6:
            raise ValueError("compiled corpus must retain 25 cases in each domain-language cell")
        primary_cells = Counter(
            (case.subtype, case.language) for case in self.cases if case.cohort_role == "primary"
        )
        canary_cells = Counter(
            (case.subtype, case.language)
            for case in self.cases
            if case.cohort_role == "compiler_canary"
        )
        if set(primary_cells.values()) != {24} or set(canary_cells.values()) != {1}:
            raise ValueError("compiled cohort is not balanced within domain-language cells")
        sequence_cells = Counter(
            (case.subtype, case.language, case.williams_sequence)
            for case in self.cases
            if case.cohort_role == "primary"
        )
        if len(sequence_cells) != 24 or set(sequence_cells.values()) != {6}:
            raise ValueError("Williams sequences are not balanced within each primary cell")
        if self.compilation_sha256 != digest_json(
            self.model_dump(mode="json", exclude={"compilation_sha256"})
        ):
            raise ValueError("autonomous compilation manifest has a stale hash")
        return self
