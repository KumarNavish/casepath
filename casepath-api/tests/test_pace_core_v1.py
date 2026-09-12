from __future__ import annotations

import ast
from copy import deepcopy
import hashlib
from pathlib import Path
import time
from typing import Any

from pydantic import ValidationError
import pytest

from casepath_api.canonicalizer import MODEL_MODE_REFERENCE
from casepath_api.claim_loop_contracts import EvidenceAction
from casepath_api.foundation.common import canonical_json_bytes, digest_value
from casepath_api.multi_agent import (
    DeterministicStructuredAgent,
    NemotronMultiAgentOrchestrator,
)
from casepath_api.pace_canonical import (
    PACECanonicalError,
    canonical_pace_json_bytes_v1,
    pace_digest_v1,
    parse_canonical_pace_json_v1,
)
from casepath_api.pace_contracts import (
    PACEActionCertificate,
    PACECapabilityOperator,
    PACECompileRequest,
    PACECompileResult,
    PACEHistoryEvent,
    PACETruthPolarity,
    PACEVerificationReceipt,
)
from casepath_api.insurance_protocol_v1 import (
    sealed_capability_operator_roster_v1,
)
from casepath_api.pace_core.compiler import (
    compile_pace_v1,
    enumerate_worlds_v1,
    unresolved_obligations_v1,
)
from casepath_api.pace_core.dev_split import (
    PACEBuildFactualHistoryPacketV1,
    PACEBuildFactualHistorySpanV1,
    PACEBuildPacketAnchorV1,
    PACEBuildInputReadinessReceiptV1,
    PACEBuildPacketManifestRowV1,
    PACEBuildPacketManifestV1,
    PACEBuildSourceRosterV1,
    PACEBuildSourceSpanRowV1,
    PACEDevCensusAnchorV1,
    PACEM0AuthorityExternalAnchorV1,
    PACEM0AuthorityV1,
    PACEOfficialDevCensusRowV1,
    PACEOfficialDevCensusRosterV1,
    assert_outcome_blind_packet_v1,
    assess_build_input_readiness_v1,
    assess_m0_v1,
    build_group_aware_split_v1,
    validate_public_dev_relative_path_v1,
)
from casepath_api.pace_core.invariant_fixture import build_invariant_request_v1
from casepath_api.pace_core.kernel_adapter import (
    PACEKernelActionProjectionV1,
    PACEKernelBlueprintV1,
    PACEKernelInputV1,
    PACEKernelObservableSnapshotV1,
    build_fixture_provenance_envelope_v1,
    compare_certificate_to_legacy_action_v1,
    compile_request_from_kernel_input_v1,
    make_kernel_input_v1,
    project_kernel_state_v1,
)
from casepath_api.pace_core.validate_fixture import (
    build_fixture_validation_receipt_v1,
)
from casepath_api.pace_core.verifier import (
    verify_certificate_v1,
    verify_compile_result_v1,
)
from casepath_api.pipeline_v15 import ClaimPipeline
from casepath_api.claim_loop_service import ClaimLoopService
from casepath_api.storage import Storage


ROOT = Path(__file__).resolve().parents[1]
PACE_ROOT = ROOT / "casepath_api" / "pace_core"
COMPILER_SHA = hashlib.sha256((PACE_ROOT / "compiler.py").read_bytes()).hexdigest()
VERIFIER_SHA = hashlib.sha256((PACE_ROOT / "verifier.py").read_bytes()).hexdigest()


def _compile(request: PACECompileRequest):
    return compile_pace_v1(
        request,
        compiler_source_sha256=COMPILER_SHA,
        verifier_source_sha256=VERIFIER_SHA,
    )


def _rehash_request(
    value: dict[str, Any], *, refresh_branch_provenance: bool = True
) -> PACECompileRequest:
    graph = value["state"]["graph"]
    graph["graph_sha256"] = pace_digest_v1(
        {key: item for key, item in graph.items() if key != "graph_sha256"}
    )
    for observation in value["state"]["observations"]:
        observation["observation_sha256"] = pace_digest_v1(
            {
                key: item
                for key, item in observation.items()
                if key != "observation_sha256"
            }
        )
    if refresh_branch_provenance:
        refreshed = []
        for branch in graph["branches"]:
            predicates = {
                atom["predicate_id"]
                for clause in branch["condition"]["clauses"]
                for atom in clause["atoms"]
            }
            observations = [
                observation
                for observation in value["state"]["observations"]
                if observation["predicate_id"] in predicates
            ]
            refreshed.append(
                {
                    "branch_id": branch["branch_id"],
                    "graph_sha256": graph["graph_sha256"],
                    "observation_ids": sorted(
                        observation["observation_id"] for observation in observations
                    ),
                    "source_locator_bindings": [
                        {"source_id": source_id, "locator_id": locator_id}
                        for source_id, locator_id in sorted(
                            {
                                (
                                    observation["source_id"],
                                    observation["locator_id"],
                                )
                                for observation in observations
                            }
                        )
                    ],
                }
            )
        value["state"]["branch_provenance"] = sorted(
            refreshed, key=lambda item: item["branch_id"]
        )
    for binding in value["state"]["branch_provenance"]:
        binding["graph_sha256"] = graph["graph_sha256"]
        binding["binding_sha256"] = pace_digest_v1(
            {key: item for key, item in binding.items() if key != "binding_sha256"}
        )
    state = value["state"]
    for event in state["history"]:
        event["event_sha256"] = pace_digest_v1(
            {key: item for key, item in event.items() if key != "event_sha256"}
        )
    state["predecessor_event_sha256"] = state["history"][-1]["event_sha256"]
    state["state_sha256"] = pace_digest_v1(
        {key: item for key, item in state.items() if key != "state_sha256"}
    )
    config = value["config"]
    config["config_sha256"] = pace_digest_v1(
        {key: item for key, item in config.items() if key != "config_sha256"}
    )
    value["request_sha256"] = pace_digest_v1(
        {key: item for key, item in value.items() if key != "request_sha256"}
    )
    return PACECompileRequest.model_validate_json(canonical_pace_json_bytes_v1(value))


def _mutate_request(
    mutator, *, refresh_branch_provenance: bool = True
) -> PACECompileRequest:
    value = build_invariant_request_v1().model_dump(mode="json")
    mutator(value)
    return _rehash_request(value, refresh_branch_provenance=refresh_branch_provenance)


def _rehash_certificate(value: dict[str, Any]) -> PACEActionCertificate:
    value["certificate_sha256"] = pace_digest_v1(
        {key: item for key, item in value.items() if key != "certificate_sha256"}
    )
    return PACEActionCertificate.model_validate_json(
        canonical_pace_json_bytes_v1(value)
    )


def test_fixture_compiles_and_independent_verifier_accepts() -> None:
    request = build_invariant_request_v1()
    result = _compile(request)
    assert result.terminal_state == "ACTION_SELECTED"
    assert result.certificate is not None
    assert result.certificate.action_id == "action.acquire_causation"
    assert result.certificate.hidden_oracle_inputs_read is False
    assert result.rejected_action_reasons == (
        "action.acquire_causation_expensive:DOMINATED",
        "action.orphan:OBLIGATION_PROCESS_NODE_MISMATCH",
    )
    receipt = verify_certificate_v1(
        request,
        result.certificate,
        expected_compiler_source_sha256=COMPILER_SHA,
        verifier_source_sha256=VERIFIER_SHA,
    )
    assert receipt.valid is True
    assert receipt.failure_codes == ()
    assert receipt.checked_world_count == 2


def test_compiler_replay_is_byte_identical() -> None:
    request = build_invariant_request_v1()
    values = {
        canonical_pace_json_bytes_v1(_compile(request).model_dump(mode="json"))
        for _ in range(20)
    }
    assert len(values) == 1


def test_standalone_fixture_receipt_is_complete_and_self_hashed() -> None:
    receipt = build_fixture_validation_receipt_v1(
        compiler_source_sha256=COMPILER_SHA,
        verifier_source_sha256=VERIFIER_SHA,
    )
    assert receipt["status"] == "PASS"
    assert receipt["activity"] == {
        "model_calls": 0,
        "provider_calls": 0,
        "credential_reads": 0,
        "may_identities_read": 0,
        "may_contents_read": 0,
        "outcomes_read": 0,
        "spend_usd_micros": 0,
    }
    assert receipt["fixture_receipt_sha256"] == pace_digest_v1(
        {
            key: value
            for key, value in receipt.items()
            if key != "fixture_receipt_sha256"
        }
    )


def test_verifier_rejects_rehashed_locator_substitution() -> None:
    request = build_invariant_request_v1()
    certificate = _compile(request).certificate
    assert certificate is not None
    value = certificate.model_dump(mode="json")
    value["locator_ids"] = ["locator.timeliness_field"]
    value["source_locator_bindings"] = [
        {
            "source_id": "source.medical_record",
            "locator_id": "locator.timeliness_field",
        }
    ]
    forged = _rehash_certificate(value)
    receipt = verify_certificate_v1(
        request,
        forged,
        expected_compiler_source_sha256=COMPILER_SHA,
        verifier_source_sha256=VERIFIER_SHA,
    )
    assert receipt.valid is False
    assert "CERTIFICATE_CONTENT_MISMATCH" in receipt.failure_codes


def test_verifier_rejects_wrong_bound_source_identity() -> None:
    request = build_invariant_request_v1()
    certificate = _compile(request).certificate
    assert certificate is not None
    receipt = verify_certificate_v1(
        request,
        certificate,
        expected_compiler_source_sha256="0" * 64,
        verifier_source_sha256=VERIFIER_SHA,
    )
    assert receipt.valid is False
    assert "COMPILER_SOURCE_IDENTITY_MISMATCH" in receipt.failure_codes


def test_undeclared_locator_is_never_emitted() -> None:
    def mutate(value: dict[str, Any]) -> None:
        value["actions"] = [deepcopy(value["actions"][0])]
        value["actions"][0]["locator_ids"] = ["locator.not_declared"]
        value["actions"][0]["source_locator_bindings"] = [
            {
                "source_id": "source.medical_record",
                "locator_id": "locator.not_declared",
            }
        ]

    result = _compile(_mutate_request(mutate))
    assert result.terminal_state == "NO_ADMISSIBLE_ACTION"
    assert result.certificate is None
    assert result.rejected_action_reasons == (
        "action.acquire_causation:UNDECLARED_LOCATOR",
    )


def test_incomplete_inherited_provenance_is_never_emitted() -> None:
    def mutate(value: dict[str, Any]) -> None:
        value["state"]["branch_provenance"] = value["state"]["branch_provenance"][1:]
        value["actions"] = [deepcopy(value["actions"][0])]

    with pytest.raises(ValidationError, match="exact graph branch roster"):
        _mutate_request(mutate, refresh_branch_provenance=False)


def test_branch_provenance_must_cite_every_relevant_observation() -> None:
    def mutate(value: dict[str, Any]) -> None:
        source = value["state"]["sources"][0]
        value["state"]["observations"].append(
            {
                "contract": "casepath.pace-observation/1.0.0",
                "observation_id": "observation.causation_direct",
                "predicate_id": "causation_supported",
                "allowed_values": ["false"],
                "polarity": PACETruthPolarity.SUPPORTS.value,
                "source_id": source["source_id"],
                "source_version": source["source_version"],
                "locator_id": "locator.causation_section",
                "observed_at": "2026-04-30T12:00:00+00:00",
                "reliability_milli": 1000,
            }
        )
        value["state"]["observations"].sort(key=lambda item: item["observation_id"])

    with pytest.raises(ValidationError, match="cite every relevant observation"):
        _mutate_request(mutate, refresh_branch_provenance=False)


def test_action_cannot_address_an_obligation_on_another_process_node() -> None:
    def mutate(value: dict[str, Any]) -> None:
        value["actions"] = [deepcopy(value["actions"][0])]
        value["actions"][0]["process_node_id"] = "acquire_causation_support"
        value["actions"][0]["process_topological_index"] = 3

    result = _compile(_mutate_request(mutate))
    assert result.terminal_state == "NO_ADMISSIBLE_ACTION"
    assert result.rejected_action_reasons == (
        "action.acquire_causation:OBLIGATION_PROCESS_NODE_MISMATCH",
    )


def test_terminal_process_nodes_cannot_emit_evidence_actions() -> None:
    def invalid_graph(value: dict[str, Any]) -> None:
        node = next(
            item
            for item in value["state"]["graph"]["nodes"]
            if item["node_id"] == "evidence_gap_causation"
        )
        node["node_kind"] = "terminal"

    with pytest.raises(ValidationError, match="terminal process nodes"):
        _mutate_request(invalid_graph)

    def terminal_action(value: dict[str, Any]) -> None:
        value["obligations"][0]["process_node_id"] = "merits_review"
        value["actions"] = [deepcopy(value["actions"][0])]
        value["actions"][0]["process_node_id"] = "merits_review"
        value["actions"][0]["process_topological_index"] = 4

    result = _compile(_mutate_request(terminal_action))
    assert result.terminal_state == "NO_ADMISSIBLE_ACTION"
    assert result.rejected_action_reasons == (
        "action.acquire_causation:PROCESS_NODE_KIND_INVALID",
    )


def test_semantically_unreachable_process_node_is_never_actionable() -> None:
    def mutate(value: dict[str, Any]) -> None:
        graph = value["state"]["graph"]
        graph["nodes"].append(
            {
                "node_id": "unreachable_action_node",
                "node_kind": "evidence",
                "topological_index": 5,
            }
        )
        graph["nodes"].sort(key=lambda item: item["node_id"])
        graph["branches"].append(
            {
                "branch_id": "branch.unreachable_child",
                "process_node_id": "acquire_causation_support",
                "target_node_id": "unreachable_action_node",
                "decision_id": "decision.unreachable_child",
                "condition": {
                    "operator": "DNF",
                    "clauses": [
                        {
                            "atoms": [
                                {
                                    "predicate_id": "causation_supported",
                                    "value": "true",
                                }
                            ]
                        }
                    ],
                },
                "material": True,
            }
        )
        graph["branches"].sort(key=lambda item: item["branch_id"])
        graph["edges"].append(
            {
                "edge_id": "edge.unreachable_child",
                "source_node_id": "acquire_causation_support",
                "target_node_id": "unreachable_action_node",
                "branch_id": "branch.unreachable_child",
            }
        )
        graph["edges"].sort(key=lambda item: item["edge_id"])
        graph["critical_decision_ids"].append("decision.unreachable_child")
        graph["critical_decision_ids"].sort()
        value["obligations"][0]["process_node_id"] = "unreachable_action_node"
        value["actions"] = [deepcopy(value["actions"][0])]
        value["actions"][0]["process_node_id"] = "unreachable_action_node"
        value["actions"][0]["process_topological_index"] = 5

    request = _mutate_request(mutate)
    assert all(
        "unreachable_action_node" not in world.reachable_node_ids
        for world in enumerate_worlds_v1(request)
    )
    result = _compile(request)
    assert result.terminal_state == "NO_ADMISSIBLE_ACTION"
    assert result.rejected_action_reasons == (
        "action.acquire_causation:ORPHAN_OR_INACTIVE_PROCESS_NODE",
    )


def test_certificate_inherits_upstream_active_branch_provenance() -> None:
    def mutate(value: dict[str, Any]) -> None:
        graph = value["state"]["graph"]
        graph["branches"].append(
            {
                "branch_id": "branch.timely_route",
                "process_node_id": "entry",
                "target_node_id": "evidence_gap_causation",
                "decision_id": "decision.timely_route",
                "condition": {
                    "operator": "DNF",
                    "clauses": [
                        {
                            "atoms": [
                                {
                                    "predicate_id": "claim_timely",
                                    "value": "true",
                                }
                            ]
                        }
                    ],
                },
                "material": True,
            }
        )
        graph["branches"].sort(key=lambda item: item["branch_id"])
        edge = next(item for item in graph["edges"] if item["edge_id"] == "edge.entry")
        edge["branch_id"] = "branch.timely_route"
        graph["critical_decision_ids"].append("decision.timely_route")
        graph["critical_decision_ids"].sort()

    result = _compile(_mutate_request(mutate))
    assert result.terminal_state == "ACTION_SELECTED"
    assert result.certificate is not None
    assert tuple(
        value.branch_id for value in result.certificate.active_chain_provenance
    ) == ("branch.timely_route",)


def test_action_node_must_be_reachable_in_every_feasible_world() -> None:
    def mutate(value: dict[str, Any]) -> None:
        value["obligations"][0]["process_node_id"] = "acquire_causation_support"
        value["actions"] = [deepcopy(value["actions"][0])]
        value["actions"][0]["process_node_id"] = "acquire_causation_support"
        value["actions"][0]["process_topological_index"] = 3

    result = _compile(_mutate_request(mutate))
    assert result.terminal_state == "NO_ADMISSIBLE_ACTION"
    assert result.rejected_action_reasons == (
        "action.acquire_causation:ORPHAN_OR_INACTIVE_PROCESS_NODE",
    )


def test_invalid_temporal_source_is_never_emitted() -> None:
    def mutate(value: dict[str, Any]) -> None:
        value["state"]["sources"][0]["valid_until"] = "2026-04-01T00:00:00+00:00"
        value["actions"] = [deepcopy(value["actions"][0])]

    result = _compile(_mutate_request(mutate))
    assert result.terminal_state == "NO_ADMISSIBLE_ACTION"
    assert result.rejected_action_reasons == (
        "action.acquire_causation:SOURCE_TEMPORAL_VALIDITY_INVALID",
    )


def test_unauthorized_observation_does_not_constrain_worlds_or_authorize_action() -> (
    None
):
    def mutate(value: dict[str, Any]) -> None:
        source = value["state"]["sources"][0]
        source["authority_valid"] = False
        value["state"]["observations"].append(
            {
                "contract": "casepath.pace-observation/1.0.0",
                "observation_id": "observation.unauthorized_causation",
                "predicate_id": "causation_supported",
                "allowed_values": ["true"],
                "polarity": PACETruthPolarity.SUPPORTS.value,
                "source_id": source["source_id"],
                "source_version": source["source_version"],
                "locator_id": "locator.causation_section",
                "observed_at": "2026-04-30T12:00:00+00:00",
                "reliability_milli": 1000,
            }
        )
        value["state"]["observations"].sort(key=lambda item: item["observation_id"])
        value["actions"] = [deepcopy(value["actions"][0])]

    request = _mutate_request(mutate)
    assert len(enumerate_worlds_v1(request)) == 4
    result = _compile(request)
    assert result.terminal_state == "NO_ADMISSIBLE_ACTION"
    assert result.rejected_action_reasons == (
        "action.acquire_causation:SOURCE_AUTHORITY_INVALID",
    )


def test_action_topological_index_must_match_the_graph() -> None:
    def mutate(value: dict[str, Any]) -> None:
        value["actions"] = [deepcopy(value["actions"][0])]
        value["actions"][0]["process_topological_index"] = 999

    result = _compile(_mutate_request(mutate))
    assert result.terminal_state == "NO_ADMISSIBLE_ACTION"
    assert result.rejected_action_reasons == (
        "action.acquire_causation:PROCESS_TOPOLOGICAL_INDEX_MISMATCH",
    )


def test_capability_algebra_is_enforced() -> None:
    def mutate(value: dict[str, Any]) -> None:
        value["actions"] = [deepcopy(value["actions"][0])]
        value["actions"][0]["capability_ids"] = ["capability.fact_causation"]

    result = _compile(_mutate_request(mutate))
    assert result.terminal_state == "NO_ADMISSIBLE_ACTION"
    assert "CAPABILITY_ROSTER_NOT_GRAPH_DERIVED" in result.rejected_action_reasons[0]


def test_capability_operator_roster_and_or_path_are_sealed() -> None:
    assert sealed_capability_operator_roster_v1() == (
        PACECapabilityOperator.CAPABILITY.value,
        PACECapabilityOperator.AND.value,
        PACECapabilityOperator.OR.value,
    )

    def mutate(value: dict[str, Any]) -> None:
        value["obligations"][0]["evidence_capability"]["operator"] = "OR"

    request = _mutate_request(mutate)
    result = _compile(request)
    assert result.certificate is not None
    expression = result.certificate.evidence_capability_expressions[0]
    assert expression.operator is PACECapabilityOperator.OR
    assert (
        verify_compile_result_v1(
            request=request,
            result=result,
            expected_compiler_source_sha256=COMPILER_SHA,
            verifier_source_sha256=VERIFIER_SHA,
        )
        == ()
    )


@pytest.mark.parametrize("alias", ("ALL_OF", "ANY_OF"))
def test_capability_operator_documentary_aliases_are_rejected(alias: str) -> None:
    with pytest.raises(ValidationError):

        def mutate(value: dict[str, Any]) -> None:
            value["obligations"][0]["evidence_capability"]["operator"] = alias

        _mutate_request(mutate)


def test_action_cannot_claim_capability_without_every_required_source() -> None:
    def mutate(value: dict[str, Any]) -> None:
        value["state"]["graph"]["capability_specs"][0]["source_ids"] = [
            "source.medical_record",
            "source.second_authority",
        ]
        value["state"]["graph"]["capability_specs"][0]["source_locator_bindings"] = [
            {
                "source_id": "source.medical_record",
                "locator_id": "locator.causation_section",
            },
            {
                "source_id": "source.second_authority",
                "locator_id": "locator.causation_section",
            },
        ]
        value["state"]["sources"].append(
            {
                **deepcopy(value["state"]["sources"][0]),
                "source_id": "source.second_authority",
                "source_sha256": "8" * 64,
            }
        )
        value["state"]["sources"].sort(key=lambda item: item["source_id"])
        value["actions"] = [deepcopy(value["actions"][0])]

    result = _compile(_mutate_request(mutate))
    assert result.terminal_state == "NO_ADMISSIBLE_ACTION"
    assert result.rejected_action_reasons == (
        "action.acquire_causation:CAPABILITY_ROSTER_NOT_GRAPH_DERIVED",
    )


def test_non_exact_locator_capability_accepts_only_a_declared_source_locator() -> None:
    def mutate(value: dict[str, Any]) -> None:
        for capability in value["state"]["graph"]["capability_specs"]:
            capability["requires_exact_locator"] = False
        value["actions"] = [deepcopy(value["actions"][0])]
        value["actions"][0]["locator_ids"] = ["locator.timeliness_field"]
        value["actions"][0]["source_locator_bindings"] = [
            {
                "source_id": "source.medical_record",
                "locator_id": "locator.timeliness_field",
            }
        ]

    result = _compile(_mutate_request(mutate))
    assert result.terminal_state == "ACTION_SELECTED"
    assert result.certificate is not None
    assert result.certificate.action_id == "action.acquire_causation"


@pytest.mark.parametrize(
    ("polarity", "reliability", "expected_worlds"),
    (
        (PACETruthPolarity.SUPPORTS.value, 999, 2),
        (PACETruthPolarity.CONFLICTS.value, 1000, 2),
        (PACETruthPolarity.REFUTES.value, 1000, 1),
    ),
)
def test_observation_polarity_reliability_and_conflict_are_not_blind_intersections(
    polarity: str,
    reliability: int,
    expected_worlds: int,
) -> None:
    def mutate(value: dict[str, Any]) -> None:
        source = value["state"]["sources"][0]
        value["state"]["observations"].append(
            {
                "contract": "casepath.pace-observation/1.0.0",
                "observation_id": "observation.causation_semantics",
                "predicate_id": "causation_supported",
                "allowed_values": ["false"],
                "polarity": polarity,
                "source_id": source["source_id"],
                "source_version": source["source_version"],
                "locator_id": "locator.causation_section",
                "observed_at": "2026-04-30T12:00:00+00:00",
                "reliability_milli": reliability,
            }
        )
        value["state"]["observations"].sort(key=lambda item: item["observation_id"])

    assert len(enumerate_worlds_v1(_mutate_request(mutate))) == expected_worlds


def test_action_capabilities_must_be_derived_from_graph_catalog() -> None:
    def mutate(value: dict[str, Any]) -> None:
        for capability in value["state"]["graph"]["capability_specs"]:
            capability["evidence_item_id"] = "evidence.different"
        value["actions"] = [deepcopy(value["actions"][0])]

    result = _compile(_mutate_request(mutate))
    assert result.terminal_state == "NO_ADMISSIBLE_ACTION"
    assert result.rejected_action_reasons == (
        "action.acquire_causation:CAPABILITY_ROSTER_NOT_GRAPH_DERIVED",
    )


def test_outcome_partition_must_inform_the_addressed_obligation() -> None:
    def mutate(value: dict[str, Any]) -> None:
        value["state"]["graph"]["predicate_specs"].append(
            {"predicate_id": "noise", "domain": ["a", "b"], "semantic_type": "state"}
        )
        value["state"]["graph"]["predicate_specs"].sort(
            key=lambda item: item["predicate_id"]
        )
        for capability in value["state"]["graph"]["capability_specs"]:
            capability["predicate_ids"] = ["noise"]
        value["actions"] = [deepcopy(value["actions"][0])]
        value["actions"][0]["outcomes"] = [
            {
                "outcome_id": "outcome.a",
                "restrictions": [{"predicate_id": "noise", "value": "a"}],
            },
            {
                "outcome_id": "outcome.b",
                "restrictions": [{"predicate_id": "noise", "value": "b"}],
            },
        ]

    result = _compile(_mutate_request(mutate))
    assert result.terminal_state == "NO_ADMISSIBLE_ACTION"
    assert result.rejected_action_reasons == (
        "action.acquire_causation:CAPABILITY_PREDICATE_COVERAGE_INCOMPLETE",
    )


def test_material_branches_do_not_collapse_when_decision_ids_match() -> None:
    def mutate(value: dict[str, Any]) -> None:
        graph = value["state"]["graph"]
        for branch in graph["branches"]:
            branch["decision_id"] = "decision.same"
        graph["critical_decision_ids"] = ["decision.same"]
        obligation = value["obligations"][0]
        obligation["predicate_ids"] = ["claim_timely"]
        obligation["target_atoms"] = [{"predicate_id": "claim_timely", "value": "true"}]

    result = _compile(_mutate_request(mutate))
    assert result.terminal_state == "NO_ADMISSIBLE_ACTION"
    worlds = enumerate_worlds_v1(_mutate_request(mutate))
    assert len({world.material_branch_ids for world in worlds}) == 2


@pytest.mark.parametrize(
    ("operator", "expected_open_ids"),
    (
        ("ALL_OF", ("obligation.establish_causation",)),
        ("ANY_OF", ()),
    ),
)
def test_obligation_conjunction_and_alternatives_are_executable(
    operator: str,
    expected_open_ids: tuple[str, ...],
) -> None:
    def mutate(value: dict[str, Any]) -> None:
        template = deepcopy(value["obligations"][0])
        template.update(
            {
                "obligation_id": "obligation.establish_timeliness",
                "predicate_ids": ["claim_timely"],
                "target_atoms": [{"predicate_id": "claim_timely", "value": "true"}],
            }
        )
        value["obligations"].append(template)
        value["obligations"].sort(key=lambda item: item["obligation_id"])
        leaves = [
            {
                "operator": "OBLIGATION",
                "obligation_id": item["obligation_id"],
                "children": [],
                "condition": None,
                "temporal_at": None,
            }
            for item in value["obligations"]
        ]
        leaves.sort(key=pace_digest_v1)
        value["obligation_expression"] = {
            "operator": operator,
            "obligation_id": None,
            "children": leaves,
            "condition": None,
            "temporal_at": None,
        }

    request = _mutate_request(mutate)
    open_ids = tuple(
        value.obligation_id
        for value in unresolved_obligations_v1(request, enumerate_worlds_v1(request))
    )
    assert open_ids == expected_open_ids


def test_conditional_and_temporal_obligation_wrappers_are_executable() -> None:
    def wrap(value: dict[str, Any], *, operator: str, active: bool) -> None:
        child = value["obligation_expression"]
        if operator == "CONDITIONAL":
            value["obligation_expression"] = {
                "operator": operator,
                "obligation_id": None,
                "children": [child],
                "condition": {
                    "operator": "DNF",
                    "clauses": [
                        {
                            "atoms": [
                                {
                                    "predicate_id": "claim_timely",
                                    "value": "true" if active else "false",
                                }
                            ]
                        }
                    ],
                },
                "temporal_at": None,
            }
        else:
            value["obligation_expression"] = {
                "operator": operator,
                "obligation_id": None,
                "children": [child],
                "condition": None,
                "temporal_at": (
                    "2026-01-01T00:00:00+00:00"
                    if active
                    else "2027-01-01T00:00:00+00:00"
                ),
            }

    for operator in ("CONDITIONAL", "TEMPORAL"):
        active = _mutate_request(
            lambda value, op=operator: wrap(value, operator=op, active=True)
        )
        inactive = _mutate_request(
            lambda value, op=operator: wrap(value, operator=op, active=False)
        )
        worlds = enumerate_worlds_v1(active)
        assert tuple(
            item.obligation_id for item in unresolved_obligations_v1(active, worlds)
        ) == ("obligation.establish_causation",)
        assert unresolved_obligations_v1(inactive, enumerate_worlds_v1(inactive)) == ()


def test_conditional_obligation_is_evaluated_only_on_its_condition_worlds() -> None:
    def wrap(value: dict[str, Any], condition_value: str) -> None:
        child = deepcopy(value["obligation_expression"])
        value["obligation_expression"] = {
            "operator": "CONDITIONAL",
            "obligation_id": None,
            "children": [child],
            "condition": {
                "operator": "DNF",
                "clauses": [
                    {
                        "atoms": [
                            {
                                "predicate_id": "causation_supported",
                                "value": condition_value,
                            }
                        ]
                    }
                ],
            },
            "temporal_at": None,
        }

    resolved = _mutate_request(lambda value: wrap(value, "true"))
    unresolved = _mutate_request(lambda value: wrap(value, "false"))
    assert unresolved_obligations_v1(resolved, enumerate_worlds_v1(resolved)) == ()
    assert tuple(
        value.obligation_id
        for value in unresolved_obligations_v1(
            unresolved, enumerate_worlds_v1(unresolved)
        )
    ) == ("obligation.establish_causation",)


def _conditional_scope_action_request(*, informative_within_scope: bool):
    def mutate(value: dict[str, Any]) -> None:
        value["state"]["observations"] = []
        if informative_within_scope:
            value["state"]["graph"]["constraints"] = []
            outcomes = [
                {
                    "outcome_id": "outcome.false",
                    "restrictions": [
                        {"predicate_id": "claim_timely", "value": "false"}
                    ],
                },
                {
                    "outcome_id": "outcome.true",
                    "restrictions": [{"predicate_id": "claim_timely", "value": "true"}],
                },
            ]
        else:
            value["state"]["graph"]["constraints"] = [
                {
                    "constraint_id": "constraint.xor",
                    "condition": {
                        "operator": "DNF",
                        "clauses": [
                            {
                                "atoms": [
                                    {
                                        "predicate_id": "causation_supported",
                                        "value": "false",
                                    },
                                    {
                                        "predicate_id": "claim_timely",
                                        "value": "true",
                                    },
                                ]
                            },
                            {
                                "atoms": [
                                    {
                                        "predicate_id": "causation_supported",
                                        "value": "true",
                                    },
                                    {
                                        "predicate_id": "claim_timely",
                                        "value": "false",
                                    },
                                ]
                            },
                        ],
                    },
                }
            ]
            outcomes = [
                {
                    "outcome_id": "outcome.false",
                    "restrictions": [
                        {
                            "predicate_id": "causation_supported",
                            "value": "false",
                        },
                        {"predicate_id": "claim_timely", "value": "true"},
                    ],
                },
                {
                    "outcome_id": "outcome.true",
                    "restrictions": [
                        {
                            "predicate_id": "causation_supported",
                            "value": "true",
                        },
                        {"predicate_id": "claim_timely", "value": "false"},
                    ],
                },
            ]
        value["obligations"][0].update(
            {
                "predicate_ids": ["claim_timely"],
                "target_atoms": [{"predicate_id": "claim_timely", "value": "true"}],
            }
        )
        value["obligation_expression"] = {
            "operator": "CONDITIONAL",
            "obligation_id": None,
            "children": [
                {
                    "operator": "OBLIGATION",
                    "obligation_id": "obligation.establish_causation",
                    "children": [],
                    "condition": None,
                    "temporal_at": None,
                }
            ],
            "condition": {
                "operator": "DNF",
                "clauses": [
                    {
                        "atoms": [
                            {
                                "predicate_id": "causation_supported",
                                "value": "true",
                            }
                        ]
                    }
                ],
            },
            "temporal_at": None,
        }
        for capability in value["state"]["graph"]["capability_specs"]:
            capability["predicate_ids"] = ["claim_timely"]
        value["actions"] = [deepcopy(value["actions"][0])]
        value["actions"][0]["outcomes"] = outcomes

    return _mutate_request(mutate)


def test_conditional_action_must_inform_within_its_effective_world_scope() -> None:
    request = _conditional_scope_action_request(informative_within_scope=False)
    result = _compile(request)
    assert result.terminal_state == "NO_ADMISSIBLE_ACTION"
    assert result.rejected_action_reasons == (
        "action.acquire_causation:OUTCOME_DOES_NOT_RESOLVE_ADDRESSED_OBLIGATION",
    )
    assert (
        verify_compile_result_v1(
            request,
            result,
            expected_compiler_source_sha256=COMPILER_SHA,
            verifier_source_sha256=VERIFIER_SHA,
        )
        == ()
    )


def test_conditional_action_certificate_carries_its_effective_world_scope() -> None:
    request = _conditional_scope_action_request(informative_within_scope=True)
    result = _compile(request)
    assert result.terminal_state == "ACTION_SELECTED"
    assert result.certificate is not None
    assert len(result.certificate.feasible_world_sha256s) == 4
    assert len(result.certificate.obligation_world_scopes) == 1
    scope = result.certificate.obligation_world_scopes[0]
    assert scope.obligation_id == "obligation.establish_causation"
    assert len(scope.world_sha256s) == 2
    verification = verify_certificate_v1(
        request,
        result.certificate,
        expected_compiler_source_sha256=COMPILER_SHA,
        verifier_source_sha256=VERIFIER_SHA,
    )
    assert verification.valid is True


def test_obligation_activation_scope_controls_dominance_and_certificate() -> None:
    def mutate(value: dict[str, Any]) -> None:
        value["state"]["observations"] = []
        value["obligations"][0].update(
            {
                "predicate_ids": ["claim_timely"],
                "target_atoms": [{"predicate_id": "claim_timely", "value": "true"}],
                "activation": {
                    "operator": "DNF",
                    "clauses": [
                        {
                            "atoms": [
                                {
                                    "predicate_id": "causation_supported",
                                    "value": "true",
                                }
                            ]
                        }
                    ],
                },
            }
        )
        for capability in value["state"]["graph"]["capability_specs"]:
            capability["action_kinds"] = ["acquire", "validate"]
            capability["predicate_ids"] = ["claim_timely"]
        cheap = deepcopy(value["actions"][0])
        cheap["outcomes"] = [
            {
                "outcome_id": "outcome.cheap.false",
                "restrictions": [{"predicate_id": "claim_timely", "value": "false"}],
            },
            {
                "outcome_id": "outcome.cheap.true",
                "restrictions": [{"predicate_id": "claim_timely", "value": "true"}],
            },
        ]
        cheap["burden_cost"] = 1
        expensive = deepcopy(cheap)
        expensive["action_id"] = "action.validate_expensive"
        expensive["action_kind"] = "validate"
        expensive["burden_cost"] = 2
        expensive["outcomes"] = [
            {
                "outcome_id": f"outcome.expensive.{p_value}.{q_value}",
                "restrictions": [
                    {
                        "predicate_id": "causation_supported",
                        "value": p_value,
                    },
                    {"predicate_id": "claim_timely", "value": q_value},
                ],
            }
            for p_value in ("false", "true")
            for q_value in ("false", "true")
        ]
        value["actions"] = [cheap, expensive]

    request = _mutate_request(mutate)
    result = _compile(request)
    assert result.terminal_state == "ACTION_SELECTED"
    assert result.certificate is not None
    assert result.certificate.action_id == "action.acquire_causation"
    assert result.certificate.accepted_action_alternative_ids == (
        "action.acquire_causation",
    )
    assert len(result.certificate.feasible_world_sha256s) == 4
    assert len(result.certificate.obligation_world_scopes[0].world_sha256s) == 2
    assert (
        verify_certificate_v1(
            request,
            result.certificate,
            expected_compiler_source_sha256=COMPILER_SHA,
            verifier_source_sha256=VERIFIER_SHA,
        ).valid
        is True
    )


def test_request_rejects_impossible_obligation_target_value() -> None:
    def mutate(value: dict[str, Any]) -> None:
        value["obligations"][0]["target_atoms"][0]["value"] = "outside_domain"

    with pytest.raises(ValidationError, match="obligation target atom"):
        _mutate_request(mutate)


@pytest.mark.parametrize(
    ("predicate_id", "predicate_value"),
    [
        ("undeclared_hidden_predicate", "true"),
        ("causation_supported", "outside_domain"),
    ],
)
def test_request_rejects_uncatalogued_obligation_activation_atom(
    predicate_id: str,
    predicate_value: str,
) -> None:
    def mutate(value: dict[str, Any]) -> None:
        value["obligations"][0]["activation"] = {
            "operator": "DNF",
            "clauses": [
                {"atoms": [{"predicate_id": predicate_id, "value": predicate_value}]}
            ],
        }

    with pytest.raises(ValidationError, match="obligation activation atom"):
        _mutate_request(mutate)


@pytest.mark.parametrize(
    ("predicate_id", "predicate_value"),
    [
        ("undeclared_hidden_predicate", "true"),
        ("causation_supported", "outside_domain"),
    ],
)
def test_request_rejects_uncatalogued_expression_condition_atom(
    predicate_id: str,
    predicate_value: str,
) -> None:
    def mutate(value: dict[str, Any]) -> None:
        value["obligation_expression"] = {
            "operator": "CONDITIONAL",
            "obligation_id": None,
            "children": [deepcopy(value["obligation_expression"])],
            "condition": {
                "operator": "DNF",
                "clauses": [
                    {
                        "atoms": [
                            {"predicate_id": predicate_id, "value": predicate_value}
                        ]
                    }
                ],
            },
            "temporal_at": None,
        }

    with pytest.raises(
        ValidationError,
        match="obligation expression condition atom",
    ):
        _mutate_request(mutate)


def test_request_rejects_action_outcome_value_outside_domain() -> None:
    def mutate(value: dict[str, Any]) -> None:
        value["actions"] = [deepcopy(value["actions"][0])]
        value["actions"][0]["outcomes"][0]["restrictions"][0]["value"] = (
            "outside_domain"
        )

    with pytest.raises(ValidationError, match="action outcome atom"):
        _mutate_request(mutate)


def test_deadline_obligation_requires_a_matching_completion_event() -> None:
    def mutate(value: dict[str, Any], *, completed: bool, late: bool = False) -> None:
        obligation = value["obligations"][0]
        obligation.update(
            {
                "kind": "SATISFY_DEADLINE",
                "predicate_ids": [],
                "target_atoms": [],
                "deadline": "2026-06-01T00:00:00+00:00",
                "satisfaction_event_types": ["EVIDENCE_ACCEPTED"],
            }
        )
        if completed:
            recorded_at = (
                "2026-06-02T00:00:00+00:00" if late else "2026-05-31T00:00:00+00:00"
            )
            value["state"]["history"].append(
                {
                    "event_id": "event.evidence.accepted",
                    "event_type": "EVIDENCE_ACCEPTED",
                    "recorded_at": recorded_at,
                    "event_sha256": "3" * 64,
                }
            )
            value["state"]["current_time"] = recorded_at
            value["state"]["predecessor_event_sha256"] = "3" * 64

    missing = _mutate_request(lambda value: mutate(value, completed=False))
    on_time = _mutate_request(lambda value: mutate(value, completed=True))
    late = _mutate_request(lambda value: mutate(value, completed=True, late=True))
    assert tuple(
        value.obligation_id
        for value in unresolved_obligations_v1(missing, enumerate_worlds_v1(missing))
    ) == ("obligation.establish_causation",)
    assert unresolved_obligations_v1(on_time, enumerate_worlds_v1(on_time)) == ()
    assert tuple(
        value.obligation_id
        for value in unresolved_obligations_v1(late, enumerate_worlds_v1(late))
    ) == ("obligation.establish_causation",)


def test_history_event_hash_is_content_derived() -> None:
    payload = {
        "event_id": "event.deadline.filed",
        "event_type": "DEADLINE_FILED",
        "recorded_at": "2026-05-31T00:00:00+00:00",
    }
    valid = {
        **payload,
        "event_sha256": pace_digest_v1(payload),
    }
    PACEHistoryEvent.model_validate_json(canonical_pace_json_bytes_v1(valid))
    valid["event_type"] = "FORGED_DEADLINE_FILED"
    with pytest.raises(ValidationError, match="does not match the event"):
        PACEHistoryEvent.model_validate_json(canonical_pace_json_bytes_v1(valid))


def test_temporal_validity_obligation_uses_its_explicit_target_time() -> None:
    def mutate(value: dict[str, Any], verification_time: str) -> None:
        value["obligations"][0].update(
            {
                "kind": "VERIFY_TEMPORAL_VALIDITY",
                "predicate_ids": [],
                "target_atoms": [],
                "source_ids": ["source.medical_record"],
                "verification_time": verification_time,
            }
        )

    valid_at_target = _mutate_request(
        lambda value: mutate(value, "2026-06-01T00:00:00+00:00")
    )
    stale_at_target = _mutate_request(
        lambda value: mutate(value, "2027-01-01T00:00:00+00:00")
    )
    assert (
        unresolved_obligations_v1(valid_at_target, enumerate_worlds_v1(valid_at_target))
        == ()
    )
    assert tuple(
        value.obligation_id
        for value in unresolved_obligations_v1(
            stale_at_target,
            enumerate_worlds_v1(stale_at_target),
        )
    ) == ("obligation.establish_causation",)


def test_deadline_obligation_rejects_untyped_informational_action() -> None:
    def mutate(value: dict[str, Any]) -> None:
        value["obligations"][0].update(
            {
                "kind": "SATISFY_DEADLINE",
                "predicate_ids": [],
                "target_atoms": [],
                "deadline": "2026-06-01T00:00:00+00:00",
                "satisfaction_event_types": ["DEADLINE_FILED"],
            }
        )
        value["actions"] = [deepcopy(value["actions"][0])]

    result = _compile(_mutate_request(mutate))
    assert result.terminal_state == "NO_ADMISSIBLE_ACTION"
    assert result.rejected_action_reasons == (
        "action.acquire_causation:NON_PREDICATE_OBLIGATION_ACTION_UNSUPPORTED_V1",
    )


def test_disambiguation_requires_capability_and_outcome_coverage_for_all_facts() -> (
    None
):
    def mutate(value: dict[str, Any]) -> None:
        value["obligations"][0].update(
            {
                "kind": "DISAMBIGUATE",
                "predicate_ids": ["causation_supported", "claim_timely"],
                "target_atoms": [],
            }
        )
        value["actions"] = [deepcopy(value["actions"][0])]

    result = _compile(_mutate_request(mutate))
    assert result.terminal_state == "NO_ADMISSIBLE_ACTION"
    assert result.rejected_action_reasons == (
        "action.acquire_causation:CAPABILITY_PREDICATE_COVERAGE_INCOMPLETE",
    )


def test_overlapping_or_incomplete_outcomes_are_rejected() -> None:
    def mutate(value: dict[str, Any]) -> None:
        value["actions"] = [deepcopy(value["actions"][0])]
        value["actions"][0]["outcomes"][1]["restrictions"] = deepcopy(
            value["actions"][0]["outcomes"][0]["restrictions"]
        )

    result = _compile(_mutate_request(mutate))
    assert result.terminal_state == "NO_ADMISSIBLE_ACTION"
    assert any(
        reason.endswith("OUTCOME_PARTITION_NOT_DISJOINT_EXHAUSTIVE")
        for reason in result.rejected_action_reasons
    )


def test_contradictory_observations_produce_no_feasible_world() -> None:
    def mutate(value: dict[str, Any]) -> None:
        source = value["state"]["sources"][0]
        first = {
            "contract": "casepath.pace-observation/1.0.0",
            "observation_id": "observation.causation_false",
            "predicate_id": "causation_supported",
            "allowed_values": ["false"],
            "polarity": PACETruthPolarity.SUPPORTS.value,
            "source_id": source["source_id"],
            "source_version": source["source_version"],
            "locator_id": "locator.causation_section",
            "observed_at": "2026-04-30T12:00:00+00:00",
            "reliability_milli": 1000,
        }
        second = {**first, "observation_id": "observation.causation_true"}
        second["allowed_values"] = ["true"]
        value["state"]["observations"].extend((first, second))
        value["state"]["observations"].sort(key=lambda item: item["observation_id"])

    result = _compile(_mutate_request(mutate))
    assert result.terminal_state == "NO_FEASIBLE_WORLD"


def test_resolved_obligation_and_unanimous_world_terminalize() -> None:
    def mutate(value: dict[str, Any]) -> None:
        source = value["state"]["sources"][0]
        observation = {
            "contract": "casepath.pace-observation/1.0.0",
            "observation_id": "observation.causation_true",
            "predicate_id": "causation_supported",
            "allowed_values": ["true"],
            "polarity": PACETruthPolarity.SUPPORTS.value,
            "source_id": source["source_id"],
            "source_version": source["source_version"],
            "locator_id": "locator.causation_section",
            "observed_at": "2026-04-30T12:00:00+00:00",
            "reliability_milli": 1000,
        }
        value["state"]["observations"].append(observation)
        value["state"]["observations"].sort(key=lambda item: item["observation_id"])

    result = _compile(_mutate_request(mutate))
    assert result.terminal_state == "ALL_WORLDS_AGREE"
    assert result.unresolved_obligation_ids == ()


@pytest.mark.parametrize(
    "raw",
    (
        b'{"a":1,"a":2}',
        b'{"value":1.5}',
        b'{"value":9007199254740992}',
        '{"e\u0301":1}'.encode(),
        b'{ "a":1}',
    ),
)
def test_canonical_wire_rejects_ambiguous_values(raw: bytes) -> None:
    with pytest.raises(PACECanonicalError):
        parse_canonical_pace_json_v1(raw)


def test_closed_schema_rejects_hidden_oracle_field() -> None:
    value = build_invariant_request_v1().model_dump(mode="json")
    value["hidden_answer"] = "action.acquire_causation"
    with pytest.raises(ValidationError):
        PACECompileRequest.model_validate_json(canonical_pace_json_bytes_v1(value))


def test_outcome_blind_guard_rejects_nested_label() -> None:
    with pytest.raises(ValueError, match="forbidden outcome-bearing field"):
        assert_outcome_blind_packet_v1({"public": {"analysis": "do not read"}})
    assert_outcome_blind_packet_v1(
        {"factual_history": [{"text": "outcome-blind synthetic statement"}]}
    )
    with pytest.raises(ValueError, match="prohibited holdout/path value"):
        assert_outcome_blind_packet_v1({"status": "affirmed"})


def _m0_authority(
    expected_census_anchor_sha256: str | None = None,
    expected_build_packet_anchor_sha256: str | None = None,
    *,
    authority_origin: str = "TEST_ONLY_SYNTHETIC",
) -> PACEM0AuthorityV1:
    payload = {
        "contract": "casepath.pace-m0-authority/1.0.0",
        "predecessor_root_anchor_file_sha256": "1" * 64,
        "directive_record_semantic_sha256": "2" * 64,
        "coordinator_scope_file_sha256": "3" * 64,
        "family_deriver_source_sha256": hashlib.sha256(
            (PACE_ROOT / "dev_split.py").read_bytes()
        ).hexdigest(),
        "expected_census_anchor_sha256": expected_census_anchor_sha256,
        "expected_build_packet_anchor_sha256": (expected_build_packet_anchor_sha256),
        "authority_origin": authority_origin,
        "partition_algorithm": "group_dp_nearest_counts_v1",
        "target_counts": [120, 43, 44],
        "expected_month_counts": [46, 56, 55, 50],
    }
    return PACEM0AuthorityV1.model_validate_json(
        canonical_pace_json_bytes_v1(
            {**payload, "authority_sha256": pace_digest_v1(payload)}
        )
    )


def _synthetic_metadata_census() -> tuple[bytes, PACEDevCensusAnchorV1]:
    rows = []
    ordinal = 0
    for month, count in zip(
        ("2026-01", "2026-02", "2026-03", "2026-04"),
        (46, 56, 55, 50),
        strict=True,
    ):
        for _ in range(count):
            ordinal += 1
            row_payload = {
                "canonical_docket": f"26-{1000 + ordinal:04d}",
                "decision_month": month,
                "official_ordinal": ordinal,
                "official_source_id": "synthetic.official-index",
                "official_source_version": "synthetic-metadata-v1",
                "official_source_locator": f"index/{month}/{ordinal:04d}",
                "merit_decision": True,
                "form_ab1": False,
                "order_only_suffix": False,
            }
            rows.append(
                PACEOfficialDevCensusRowV1.model_validate_json(
                    canonical_pace_json_bytes_v1(
                        {
                            **row_payload,
                            "row_sha256": pace_digest_v1(row_payload),
                        }
                    )
                )
            )
    rows.sort(key=lambda value: value.row_sha256)
    roster_payload = {
        "contract": "casepath.pace-official-dev-census/1.0.0",
        "rows": [value.model_dump(mode="json") for value in rows],
    }
    roster = PACEOfficialDevCensusRosterV1.model_validate_json(
        canonical_pace_json_bytes_v1(
            {
                **roster_payload,
                "roster_semantic_sha256": pace_digest_v1(roster_payload),
            }
        )
    )
    roster_bytes = canonical_pace_json_bytes_v1(roster.model_dump(mode="json"))
    family_deriver_sha = hashlib.sha256(
        (PACE_ROOT / "dev_split.py").read_bytes()
    ).hexdigest()
    anchor_payload = {
        "contract": "casepath.pace-dev-census-anchor/1.0.0",
        "source_kind": "OFFICIAL_ECAB_INDEX_METADATA_ONLY",
        "roster_file_sha256": hashlib.sha256(roster_bytes).hexdigest(),
        "roster_semantic_sha256": roster.roster_semantic_sha256,
        "row_sha256s": [value.row_sha256 for value in rows],
        "month_counts": [46, 56, 55, 50],
        "family_deriver_source_sha256": family_deriver_sha,
        "source_registry_version": "synthetic-metadata-v1",
    }
    anchor = PACEDevCensusAnchorV1.model_validate_json(
        canonical_pace_json_bytes_v1(
            {**anchor_payload, "anchor_sha256": pace_digest_v1(anchor_payload)}
        )
    )
    return roster_bytes, anchor


def _synthetic_build_packets(split):
    packet_bytes_by_path: dict[str, bytes] = {}
    manifest_rows = []
    source_rows = []
    for split_row in sorted(
        (value for value in split.rows if value.partition == "build"),
        key=lambda value: value.record_id,
    ):
        span_payload = {
            "section_role": "FACTUAL_HISTORY",
            "source_id": f"synthetic.source.{split_row.record_id}",
            "source_version": "synthetic-factual-history-v1",
            "locator_id": f"factual-history/{split_row.record_id}/span-0001",
            "normalized_text": (
                f"Synthetic factual history statement for {split_row.record_id}."
            ),
        }
        span_payload["text_sha256"] = hashlib.sha256(
            span_payload["normalized_text"].encode("utf-8")
        ).hexdigest()
        span = PACEBuildFactualHistorySpanV1.model_validate_json(
            canonical_pace_json_bytes_v1(
                {**span_payload, "span_sha256": pace_digest_v1(span_payload)}
            )
        )
        source_registry_sha256 = pace_digest_v1(
            ["synthetic-source-registry-v1", split_row.record_id]
        )
        source_row_payload = {
            "record_id": split_row.record_id,
            "source_registry_sha256": source_registry_sha256,
            "span": span.model_dump(mode="json"),
        }
        source_rows.append(
            PACEBuildSourceSpanRowV1.model_validate_json(
                canonical_pace_json_bytes_v1(
                    {
                        **source_row_payload,
                        "row_sha256": pace_digest_v1(source_row_payload),
                    }
                )
            )
        )
        packet_payload = {
            "contract": "casepath.pace-outcome-blind-factual-history/1.0.0",
            "record_id": split_row.record_id,
            "source_registry_sha256": source_registry_sha256,
            "spans": [span.model_dump(mode="json")],
        }
        packet = PACEBuildFactualHistoryPacketV1.model_validate_json(
            canonical_pace_json_bytes_v1(
                {
                    **packet_payload,
                    "packet_sha256": pace_digest_v1(packet_payload),
                }
            )
        )
        packet_bytes = canonical_pace_json_bytes_v1(packet.model_dump(mode="json"))
        relative_path = f"public-dev/{split_row.record_id}.json"
        packet_bytes_by_path[relative_path] = packet_bytes
        row_payload = {
            "record_id": split_row.record_id,
            "split_row_sha256": split_row.row_sha256,
            "packet_relative_path": relative_path,
            "packet_file_sha256": hashlib.sha256(packet_bytes).hexdigest(),
            "packet_semantic_sha256": packet.packet_sha256,
            "source_registry_sha256": source_registry_sha256,
            "allowed_span_sha256s": [span.span_sha256],
        }
        manifest_rows.append(
            PACEBuildPacketManifestRowV1.model_validate_json(
                canonical_pace_json_bytes_v1(
                    {**row_payload, "row_sha256": pace_digest_v1(row_payload)}
                )
            )
        )
    manifest_payload = {
        "contract": "casepath.pace-build-packet-manifest/1.0.0",
        "split_manifest_sha256": split.manifest_sha256,
        "rows": [value.model_dump(mode="json") for value in manifest_rows],
    }
    manifest = PACEBuildPacketManifestV1.model_validate_json(
        canonical_pace_json_bytes_v1(
            {
                **manifest_payload,
                "manifest_semantic_sha256": pace_digest_v1(manifest_payload),
            }
        )
    )
    manifest_bytes = canonical_pace_json_bytes_v1(manifest.model_dump(mode="json"))
    source_roster_payload = {
        "contract": "casepath.pace-build-source-roster/1.0.0",
        "rows": [value.model_dump(mode="json") for value in source_rows],
    }
    source_roster = PACEBuildSourceRosterV1.model_validate_json(
        canonical_pace_json_bytes_v1(
            {
                **source_roster_payload,
                "roster_semantic_sha256": pace_digest_v1(source_roster_payload),
            }
        )
    )
    source_roster_bytes = canonical_pace_json_bytes_v1(
        source_roster.model_dump(mode="json")
    )
    anchor_payload = {
        "contract": "casepath.pace-build-packet-anchor/1.0.0",
        "split_manifest_sha256": split.manifest_sha256,
        "packet_manifest_file_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "packet_manifest_semantic_sha256": manifest.manifest_semantic_sha256,
        "manifest_row_sha256s": sorted(value.row_sha256 for value in manifest.rows),
        "source_roster_file_sha256": hashlib.sha256(source_roster_bytes).hexdigest(),
        "source_roster_semantic_sha256": source_roster.roster_semantic_sha256,
        "source_roster_row_sha256s": sorted(
            value.row_sha256 for value in source_roster.rows
        ),
    }
    anchor = PACEBuildPacketAnchorV1.model_validate_json(
        canonical_pace_json_bytes_v1(
            {**anchor_payload, "anchor_sha256": pace_digest_v1(anchor_payload)}
        )
    )
    return manifest_bytes, anchor, packet_bytes_by_path, source_roster_bytes


def test_m0_without_external_anchor_is_exactly_input_not_ready() -> None:
    receipt = assess_m0_v1(
        authority=_m0_authority(),
        census_anchor=None,
        census_roster_bytes=None,
    )
    assert receipt.classification == "PACE_CORE_INPUT_NOT_READY"
    assert receipt.authenticated_census_rows == 0
    assert receipt.available_build_packets == 0
    assert receipt.split_executed is False
    assert receipt.reason_codes == (
        "EXTERNAL_CENSUS_ANCHOR_ABSENT",
        "EXTERNAL_CENSUS_ROSTER_ABSENT",
    )


def test_m0_positive_path_reauthenticates_external_census_bytes() -> None:
    roster_bytes, anchor = _synthetic_metadata_census()
    authority = _m0_authority(anchor.anchor_sha256)
    manifest = build_group_aware_split_v1(
        census_roster_bytes=roster_bytes,
        census_anchor=anchor,
        authority=authority,
    )
    assert len(manifest.rows) == 207
    assert manifest.actual_counts == (120, 43, 44)
    assert manifest.exact_target_achieved is True
    assert tuple(
        sum(value.decision_month == month for value in manifest.rows)
        for month in ("2026-01", "2026-02", "2026-03", "2026-04")
    ) == (46, 56, 55, 50)
    drifted = roster_bytes.replace(
        b"synthetic-metadata-v1", b"synthetic-metadata-v2", 1
    )
    with pytest.raises(ValueError):
        build_group_aware_split_v1(
            census_roster_bytes=drifted,
            census_anchor=anchor,
            authority=authority,
        )


def test_m0_assessment_never_splits_without_both_external_inputs() -> None:
    roster_bytes, anchor = _synthetic_metadata_census()
    authority = _m0_authority(anchor.anchor_sha256)
    missing_roster = assess_m0_v1(
        authority=authority,
        census_anchor=anchor,
        census_roster_bytes=None,
    )
    assert missing_roster.classification == "PACE_CORE_INPUT_NOT_READY"
    assert missing_roster.split_executed is False
    missing_anchor = assess_m0_v1(
        authority=authority,
        census_anchor=None,
        census_roster_bytes=roster_bytes,
    )
    assert missing_anchor.classification == "PACE_CORE_INPUT_NOT_READY"
    assert missing_anchor.split_executed is False


def test_m0_build_packet_readiness_is_separate_from_split() -> None:
    authority_without_census = _m0_authority()
    pre_split = assess_build_input_readiness_v1(
        authority=authority_without_census,
        census_roster_bytes=None,
        census_anchor=None,
        split_manifest=None,
        packet_manifest_bytes=None,
        packet_anchor=None,
        packet_bytes_by_path={},
    )
    assert pre_split.classification == "PACE_CORE_INPUT_NOT_READY"
    assert pre_split.assigned_build_rows == 0
    assert pre_split.available_build_packets == 0
    assert pre_split.missing_build_packets == 120
    assert pre_split.denial_guard_status == "NOT_EXECUTED"

    roster_bytes, anchor = _synthetic_metadata_census()
    authority = _m0_authority(anchor.anchor_sha256)
    split = build_group_aware_split_v1(
        census_roster_bytes=roster_bytes,
        census_anchor=anchor,
        authority=authority,
    )
    post_split = assess_build_input_readiness_v1(
        authority=authority,
        census_roster_bytes=roster_bytes,
        census_anchor=anchor,
        split_manifest=split,
        packet_manifest_bytes=None,
        packet_anchor=None,
        packet_bytes_by_path={},
    )
    assert post_split.classification == "PACE_CORE_INPUT_NOT_READY"
    assert post_split.assigned_build_rows == 120
    assert post_split.available_build_packets == 0
    assert post_split.missing_build_packets == 120
    assert len(post_split.missing_input_inventory) == 120
    assert all(
        value.status == "MISSING"
        and value.reason_code
        == "EXTERNAL_PACKET_MANIFEST_ANCHOR_OR_SOURCE_ROSTER_ABSENT"
        for value in post_split.missing_input_inventory
    )


def test_m0_ready_path_requires_the_externally_bound_packet_anchor() -> None:
    roster_bytes, census_anchor = _synthetic_metadata_census()
    partition_authority = _m0_authority(census_anchor.anchor_sha256)
    prospective_split = build_group_aware_split_v1(
        census_roster_bytes=roster_bytes,
        census_anchor=census_anchor,
        authority=partition_authority,
    )
    (
        packet_manifest_bytes,
        packet_anchor,
        packets,
        source_roster_bytes,
    ) = _synthetic_build_packets(prospective_split)
    frozen_authority = _m0_authority(
        census_anchor.anchor_sha256,
        packet_anchor.anchor_sha256,
    )
    frozen_split = build_group_aware_split_v1(
        census_roster_bytes=roster_bytes,
        census_anchor=census_anchor,
        authority=frozen_authority,
    )
    assert frozen_split == prospective_split
    ready = assess_build_input_readiness_v1(
        authority=frozen_authority,
        census_roster_bytes=roster_bytes,
        census_anchor=census_anchor,
        split_manifest=frozen_split,
        packet_manifest_bytes=packet_manifest_bytes,
        packet_anchor=packet_anchor,
        packet_bytes_by_path=packets,
        source_roster_bytes=source_roster_bytes,
    )
    assert ready.classification == "PACE_CORE_INPUT_READY_120_TEST_ONLY"
    assert ready.available_build_packets == 120
    assert ready.missing_build_packets == 0
    assert ready.rejected_build_packets == 0
    assert len(ready.missing_input_inventory) == 120
    assert all(value.status == "AVAILABLE" for value in ready.missing_input_inventory)
    assert ready.authority_verification_status == "TEST_ONLY_SYNTHETIC"

    forged_inventory = ready.model_dump(mode="json")
    forged_inventory["missing_input_inventory"] = [
        {
            "scope": "build_factual_history",
            "record_id": None,
            "split_row_sha256": None,
            "status": "AVAILABLE",
            "reason_code": "FORGED_AGGREGATE",
            "required_count": 120,
            "available_count": 120,
            "packet_file_sha256": "4" * 64,
            "packet_semantic_sha256": "5" * 64,
            "packet_anchor_sha256": packet_anchor.anchor_sha256,
            "source_registry_sha256": "6" * 64,
        }
    ]
    forged_inventory["receipt_sha256"] = pace_digest_v1(
        {
            key: value
            for key, value in forged_inventory.items()
            if key != "receipt_sha256"
        }
    )
    with pytest.raises(ValidationError, match="exact 120-row roster"):
        PACEBuildInputReadinessReceiptV1.model_validate_json(
            canonical_pace_json_bytes_v1(forged_inventory)
        )

    wrong_authority = _m0_authority(census_anchor.anchor_sha256, "9" * 64)
    wrong_split = build_group_aware_split_v1(
        census_roster_bytes=roster_bytes,
        census_anchor=census_anchor,
        authority=wrong_authority,
    )
    assert wrong_split == prospective_split
    with pytest.raises(ValueError, match="external anchor"):
        assess_build_input_readiness_v1(
            authority=wrong_authority,
            census_roster_bytes=roster_bytes,
            census_anchor=census_anchor,
            split_manifest=wrong_split,
            packet_manifest_bytes=packet_manifest_bytes,
            packet_anchor=packet_anchor,
            packet_bytes_by_path=packets,
            source_roster_bytes=source_roster_bytes,
        )


def test_m0_v1_never_promotes_a_caller_supplied_external_tree_to_empirical_ready() -> (
    None
):
    roster_bytes, census_anchor = _synthetic_metadata_census()
    prospective_authority = _m0_authority(
        census_anchor.anchor_sha256,
        authority_origin="EXTERNAL_ROOT_BOUND",
    )
    prospective_split = build_group_aware_split_v1(
        census_roster_bytes=roster_bytes,
        census_anchor=census_anchor,
        authority=prospective_authority,
    )
    (
        packet_manifest_bytes,
        packet_anchor,
        packets,
        source_roster_bytes,
    ) = _synthetic_build_packets(prospective_split)
    authority = _m0_authority(
        census_anchor.anchor_sha256,
        packet_anchor.anchor_sha256,
        authority_origin="EXTERNAL_ROOT_BOUND",
    )
    authority_bytes = canonical_pace_json_bytes_v1(authority.model_dump(mode="json"))
    external_payload = {
        "contract": "casepath.pace-m0-authority-external-anchor/1.0.0",
        "predecessor_root_anchor_file_sha256": (
            authority.predecessor_root_anchor_file_sha256
        ),
        "directive_record_semantic_sha256": (
            authority.directive_record_semantic_sha256
        ),
        "coordinator_scope_file_sha256": authority.coordinator_scope_file_sha256,
        "authority_file_sha256": hashlib.sha256(authority_bytes).hexdigest(),
        "authority_semantic_sha256": authority.authority_sha256,
        "expected_build_packet_anchor_sha256": packet_anchor.anchor_sha256,
        "publication_state": "PREREGISTERED_BEFORE_READINESS",
    }
    external = PACEM0AuthorityExternalAnchorV1.model_validate_json(
        canonical_pace_json_bytes_v1(
            {**external_payload, "anchor_sha256": pace_digest_v1(external_payload)}
        )
    )
    split = build_group_aware_split_v1(
        census_roster_bytes=roster_bytes,
        census_anchor=census_anchor,
        authority=authority,
    )
    assert split == prospective_split

    without_external_root = assess_build_input_readiness_v1(
        authority=authority,
        census_roster_bytes=roster_bytes,
        census_anchor=census_anchor,
        split_manifest=split,
        packet_manifest_bytes=packet_manifest_bytes,
        packet_anchor=packet_anchor,
        packet_bytes_by_path=packets,
        source_roster_bytes=source_roster_bytes,
    )
    assert without_external_root.classification == "PACE_CORE_INPUT_NOT_READY"
    assert (
        without_external_root.authority_verification_status == "EXTERNAL_ROOT_MISSING"
    )

    externally_bound_but_not_promotable = assess_build_input_readiness_v1(
        authority=authority,
        authority_bytes=authority_bytes,
        authority_external_anchor=external,
        expected_authority_external_anchor_sha256=external.anchor_sha256,
        census_roster_bytes=roster_bytes,
        census_anchor=census_anchor,
        split_manifest=split,
        packet_manifest_bytes=packet_manifest_bytes,
        packet_anchor=packet_anchor,
        packet_bytes_by_path=packets,
        source_roster_bytes=source_roster_bytes,
    )
    assert (
        externally_bound_but_not_promotable.classification
        == "PACE_CORE_INPUT_NOT_READY"
    )
    assert (
        externally_bound_but_not_promotable.authority_external_anchor_sha256
        == external.anchor_sha256
    )
    assert externally_bound_but_not_promotable.available_build_packets == 120
    assert (
        externally_bound_but_not_promotable.empirical_readiness_gate
        == "DISABLED_PENDING_SEPARATELY_ROOTED_ACQUISITION_V2"
    )
    forged_ready = externally_bound_but_not_promotable.model_dump(mode="json")
    forged_ready["classification"] = "PACE_CORE_INPUT_READY_120"
    forged_ready["receipt_sha256"] = pace_digest_v1(
        {key: value for key, value in forged_ready.items() if key != "receipt_sha256"}
    )
    with pytest.raises(ValidationError):
        PACEBuildInputReadinessReceiptV1.model_validate_json(
            canonical_pace_json_bytes_v1(forged_ready)
        )

    with pytest.raises(ValueError, match="external root"):
        assess_build_input_readiness_v1(
            authority=authority,
            authority_bytes=authority_bytes,
            authority_external_anchor=external,
            expected_authority_external_anchor_sha256="9" * 64,
            census_roster_bytes=roster_bytes,
            census_anchor=census_anchor,
            split_manifest=split,
            packet_manifest_bytes=packet_manifest_bytes,
            packet_anchor=packet_anchor,
            packet_bytes_by_path=packets,
            source_roster_bytes=source_roster_bytes,
        )


def test_m0_packet_span_must_match_the_external_source_roster() -> None:
    roster_bytes, census_anchor = _synthetic_metadata_census()
    partition_authority = _m0_authority(census_anchor.anchor_sha256)
    split = build_group_aware_split_v1(
        census_roster_bytes=roster_bytes,
        census_anchor=census_anchor,
        authority=partition_authority,
    )
    manifest_bytes, original_anchor, packets, source_roster_bytes = (
        _synthetic_build_packets(split)
    )
    manifest = PACEBuildPacketManifestV1.model_validate_json(manifest_bytes)
    first = manifest.rows[0]
    packet = PACEBuildFactualHistoryPacketV1.model_validate_json(
        packets[first.packet_relative_path]
    )
    packet_value = packet.model_dump(mode="json")
    packet_value["spans"][0]["normalized_text"] = (
        "A substituted caller-authored factual-history assertion."
    )
    packet_value["spans"][0]["text_sha256"] = hashlib.sha256(
        packet_value["spans"][0]["normalized_text"].encode("utf-8")
    ).hexdigest()
    packet_value["spans"][0]["span_sha256"] = pace_digest_v1(
        {
            key: value
            for key, value in packet_value["spans"][0].items()
            if key != "span_sha256"
        }
    )
    packet_value["packet_sha256"] = pace_digest_v1(
        {key: value for key, value in packet_value.items() if key != "packet_sha256"}
    )
    substituted_packet = PACEBuildFactualHistoryPacketV1.model_validate_json(
        canonical_pace_json_bytes_v1(packet_value)
    )
    substituted_bytes = canonical_pace_json_bytes_v1(
        substituted_packet.model_dump(mode="json")
    )
    packets = dict(packets)
    packets[first.packet_relative_path] = substituted_bytes

    manifest_rows = []
    for row in manifest.rows:
        row_value = row.model_dump(mode="json")
        if row.record_id == first.record_id:
            row_value["packet_file_sha256"] = hashlib.sha256(
                substituted_bytes
            ).hexdigest()
            row_value["packet_semantic_sha256"] = substituted_packet.packet_sha256
            row_value["allowed_span_sha256s"] = sorted(
                value.span_sha256 for value in substituted_packet.spans
            )
            row_value["row_sha256"] = pace_digest_v1(
                {key: value for key, value in row_value.items() if key != "row_sha256"}
            )
        manifest_rows.append(row_value)
    manifest_value = manifest.model_dump(mode="json")
    manifest_value["rows"] = manifest_rows
    manifest_value["manifest_semantic_sha256"] = pace_digest_v1(
        {
            key: value
            for key, value in manifest_value.items()
            if key != "manifest_semantic_sha256"
        }
    )
    substituted_manifest = PACEBuildPacketManifestV1.model_validate_json(
        canonical_pace_json_bytes_v1(manifest_value)
    )
    substituted_manifest_bytes = canonical_pace_json_bytes_v1(
        substituted_manifest.model_dump(mode="json")
    )
    source_roster = PACEBuildSourceRosterV1.model_validate_json(source_roster_bytes)
    anchor_payload = {
        "contract": "casepath.pace-build-packet-anchor/1.0.0",
        "split_manifest_sha256": split.manifest_sha256,
        "packet_manifest_file_sha256": hashlib.sha256(
            substituted_manifest_bytes
        ).hexdigest(),
        "packet_manifest_semantic_sha256": (
            substituted_manifest.manifest_semantic_sha256
        ),
        "manifest_row_sha256s": sorted(
            value.row_sha256 for value in substituted_manifest.rows
        ),
        "source_roster_file_sha256": original_anchor.source_roster_file_sha256,
        "source_roster_semantic_sha256": (
            original_anchor.source_roster_semantic_sha256
        ),
        "source_roster_row_sha256s": sorted(
            value.row_sha256 for value in source_roster.rows
        ),
    }
    substituted_anchor = PACEBuildPacketAnchorV1.model_validate_json(
        canonical_pace_json_bytes_v1(
            {**anchor_payload, "anchor_sha256": pace_digest_v1(anchor_payload)}
        )
    )
    authority = _m0_authority(
        census_anchor.anchor_sha256,
        substituted_anchor.anchor_sha256,
    )
    receipt = assess_build_input_readiness_v1(
        authority=authority,
        census_roster_bytes=roster_bytes,
        census_anchor=census_anchor,
        split_manifest=build_group_aware_split_v1(
            census_roster_bytes=roster_bytes,
            census_anchor=census_anchor,
            authority=authority,
        ),
        packet_manifest_bytes=substituted_manifest_bytes,
        packet_anchor=substituted_anchor,
        packet_bytes_by_path=packets,
        source_roster_bytes=source_roster_bytes,
    )
    assert receipt.classification == "PACE_CORE_INPUT_NOT_READY"
    assert receipt.rejected_build_packets == 1
    rejected = next(
        value for value in receipt.missing_input_inventory if value.status == "REJECTED"
    )
    assert rejected.record_id == first.record_id
    assert rejected.reason_code == "PACKET_BINDING_OR_DENIAL_GUARD_FAILED"


def test_m0_packet_schema_rejects_non_factual_history_sections() -> None:
    payload = {
        "section_role": "ANALYSIS",
        "source_id": "synthetic.source",
        "source_version": "synthetic-v1",
        "locator_id": "span-1",
        "normalized_text": "Outcome-bearing section must never enter the packet.",
    }
    payload["text_sha256"] = hashlib.sha256(
        payload["normalized_text"].encode("utf-8")
    ).hexdigest()
    payload["span_sha256"] = pace_digest_v1(payload)
    with pytest.raises(ValidationError):
        PACEBuildFactualHistorySpanV1.model_validate_json(
            canonical_pace_json_bytes_v1(payload)
        )


@pytest.mark.parametrize(
    "value",
    (
        "2026-05/case.json",
        "../public-dev/case.json",
        "/public-dev/case.json",
        "public-dev/26-0247.json",
        "public-dev/gold.json",
        "public-dev/case.pdf",
    ),
)
def test_m0_preopen_guard_rejects_holdout_or_unsafe_paths(value: str) -> None:
    with pytest.raises(ValueError, match="frozen allowlist"):
        validate_public_dev_relative_path_v1(value)


@pytest.mark.parametrize(
    "key",
    (
        "analysis_text",
        "decision_outcome",
        "gold",
        "disposition",
        "final_order",
        "expected_documents",
        "hidden_target",
    ),
)
def test_m0_outcome_guard_rejects_normalized_key_families(key: str) -> None:
    with pytest.raises(ValueError, match="forbidden outcome-bearing field"):
        assert_outcome_blind_packet_v1({key: "forbidden"})


def test_compiler_and_verifier_have_disjoint_pure_closures() -> None:
    compiler_tree = ast.parse((PACE_ROOT / "compiler.py").read_text())
    verifier_tree = ast.parse((PACE_ROOT / "verifier.py").read_text())
    forbidden = {
        "os",
        "pathlib",
        "socket",
        "subprocess",
        "requests",
        "httpx",
        "sqlite3",
    }
    for tree in (compiler_tree, verifier_tree):
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                imports.add(node.module.split(".")[0])
        assert not imports.intersection(forbidden)
    assert "compiler" not in {
        node.module
        for node in ast.walk(verifier_tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }


def _fixture_kernel_input():
    base = build_invariant_request_v1()
    projections = tuple(
        PACEKernelActionProjectionV1(
            pace_action_id=action.action_id,
            action_kind=action.action_kind,
            process_node_id=action.process_node_id,
            evidence_item_id=action.evidence_item_id,
            fact_id="causation_supported",
            title=(
                "Acquire causation support"
                if action.action_id == "action.acquire_causation"
                else f"Fixture alternative {action.action_id}"
            ),
            bounded_tool_id="fixture.tool",
        )
        for action in base.actions
    )
    blueprint_payload = {
        "contract": "casepath.pace-kernel-blueprint/1.0.0",
        "template_version": "fixture-template-v1",
        "graph": base.state.graph.model_dump(mode="json"),
        "sources": [value.model_dump(mode="json") for value in base.state.sources],
        "obligations": [value.model_dump(mode="json") for value in base.obligations],
        "obligation_expression": base.obligation_expression.model_dump(mode="json"),
        "actions": [value.model_dump(mode="json") for value in base.actions],
        "action_projections": [value.model_dump(mode="json") for value in projections],
        "config": base.config.model_dump(mode="json"),
    }
    blueprint = PACEKernelBlueprintV1.model_validate_json(
        canonical_pace_json_bytes_v1(
            {
                **blueprint_payload,
                "blueprint_sha256": pace_digest_v1(blueprint_payload),
            }
        )
    )
    snapshot_payload = {
        "contract": "casepath.pace-kernel-observable-snapshot/1.0.0",
        "record_version": "fixture-record-v1",
        "template_version": blueprint.template_version,
        "process_version": blueprint.graph.process_version,
        "rule_version": blueprint.graph.rule_version,
        "source_registry_version": blueprint.graph.source_registry_version,
        "knowledge_version": blueprint.graph.knowledge_version,
        "observations": [
            value.model_dump(mode="json") for value in base.state.observations
        ],
        "documents": [value.model_dump(mode="json") for value in base.state.documents],
        "completed_history": [],
        "current_time": base.state.current_time,
    }
    snapshot = PACEKernelObservableSnapshotV1.model_validate_json(
        canonical_pace_json_bytes_v1(
            {**snapshot_payload, "snapshot_sha256": pace_digest_v1(snapshot_payload)}
        )
    )
    return make_kernel_input_v1(blueprint=blueprint, snapshot=snapshot)


def _compatibility_kwargs(kernel_input=None) -> dict[str, str]:
    kernel_input = kernel_input or _fixture_kernel_input()
    return {
        "expected_iteration29_root_anchor_file_sha256": "1" * 64,
        "expected_iteration29_source_manifest_file_sha256": "2" * 64,
        "expected_adapter_source_sha256": hashlib.sha256(
            (PACE_ROOT / "kernel_adapter.py").read_bytes()
        ).hexdigest(),
        "expected_blueprint_sha256": kernel_input.blueprint.blueprint_sha256,
        "expected_snapshot_sha256": kernel_input.snapshot.snapshot_sha256,
        "expected_kernel_input_sha256": kernel_input.input_sha256,
        "expected_compiler_source_sha256": COMPILER_SHA,
        "expected_verifier_source_sha256": VERIFIER_SHA,
    }


def _legacy_action_for_result(kernel_input, result) -> EvidenceAction:
    assert result.certificate is not None
    selected = next(
        value
        for value in kernel_input.blueprint.action_projections
        if value.pace_action_id == result.certificate.action_id
    )
    payload = {
        "contract": "casepath.evidence-action/1.0.0",
        "action_kind": selected.action_kind,
        "process_node_id": selected.process_node_id,
        "evidence_item_id": selected.evidence_item_id,
        "fact_id": selected.fact_id,
        "title": selected.title,
        "bounded_tool_id": selected.bounded_tool_id,
    }
    action_sha = digest_value(payload)
    return EvidenceAction(
        **payload,
        action_id=f"action.{action_sha}",
        action_sha256=action_sha,
    )


def test_kernel_blueprint_adapter_is_closed_and_shadow_only() -> None:
    kernel_input = _fixture_kernel_input()
    request = compile_request_from_kernel_input_v1(kernel_input)
    assert request == compile_request_from_kernel_input_v1(kernel_input)
    input_material = kernel_input.model_dump(mode="json")
    for forbidden in (
        "selected_action",
        "last_event_sha256",
        "expected_action",
        "gold",
        "evaluator",
        "final_claim_brief",
    ):
        assert forbidden not in input_material
    result = _compile(request)
    assert result.certificate is not None
    verification = verify_certificate_v1(
        request,
        result.certificate,
        expected_compiler_source_sha256=COMPILER_SHA,
        verifier_source_sha256=VERIFIER_SHA,
    )
    provenance = build_fixture_provenance_envelope_v1(
        kernel_input=kernel_input,
        iteration29_root_anchor_file_sha256="1" * 64,
        iteration29_source_manifest_file_sha256="2" * 64,
        adapter_source_sha256=_compatibility_kwargs(kernel_input)[
            "expected_adapter_source_sha256"
        ],
    )
    selected = next(
        value
        for value in kernel_input.blueprint.action_projections
        if value.pace_action_id == result.certificate.action_id
    )
    legacy_payload = {
        "contract": "casepath.evidence-action/1.0.0",
        "action_kind": selected.action_kind,
        "process_node_id": selected.process_node_id,
        "evidence_item_id": selected.evidence_item_id,
        "fact_id": selected.fact_id,
        "title": selected.title,
        "bounded_tool_id": selected.bounded_tool_id,
    }
    action_sha = digest_value(legacy_payload)
    legacy = EvidenceAction(
        **legacy_payload,
        action_id=f"action.{action_sha}",
        action_sha256=action_sha,
    )
    receipt = compare_certificate_to_legacy_action_v1(
        kernel_input,
        provenance,
        result,
        verification,
        legacy,
        **_compatibility_kwargs(kernel_input),
    )
    assert receipt.compatible is True
    assert receipt.shadow_only is True
    assert receipt.kernel_mutated is False


def test_kernel_adapter_rejects_forged_verifier_and_external_anchor() -> None:
    kernel_input = _fixture_kernel_input()
    request = compile_request_from_kernel_input_v1(kernel_input)
    result = _compile(request)
    assert result.certificate is not None
    actual = verify_certificate_v1(
        request,
        result.certificate,
        expected_compiler_source_sha256=COMPILER_SHA,
        verifier_source_sha256=VERIFIER_SHA,
    )
    forged_payload = {
        **actual.model_dump(mode="json"),
        "checked_world_count": 0,
    }
    forged_payload["receipt_sha256"] = pace_digest_v1(
        {key: value for key, value in forged_payload.items() if key != "receipt_sha256"}
    )
    forged = PACEVerificationReceipt.model_validate_json(
        canonical_pace_json_bytes_v1(forged_payload)
    )
    provenance = build_fixture_provenance_envelope_v1(
        kernel_input=kernel_input,
        iteration29_root_anchor_file_sha256="1" * 64,
        iteration29_source_manifest_file_sha256="2" * 64,
        adapter_source_sha256=_compatibility_kwargs(kernel_input)[
            "expected_adapter_source_sha256"
        ],
    )
    projection = next(
        value
        for value in kernel_input.blueprint.action_projections
        if value.pace_action_id == result.certificate.action_id
    )
    legacy_payload = {
        "contract": "casepath.evidence-action/1.0.0",
        "action_kind": projection.action_kind,
        "process_node_id": projection.process_node_id,
        "evidence_item_id": projection.evidence_item_id,
        "fact_id": projection.fact_id,
        "title": projection.title,
        "bounded_tool_id": projection.bounded_tool_id,
    }
    action_sha = digest_value(legacy_payload)
    legacy = EvidenceAction(
        **legacy_payload,
        action_id=f"action.{action_sha}",
        action_sha256=action_sha,
    )
    rejected = compare_certificate_to_legacy_action_v1(
        kernel_input,
        provenance,
        result,
        forged,
        legacy,
        **_compatibility_kwargs(kernel_input),
    )
    assert rejected.compatible is False
    assert "VERIFICATION_RECOMPUTATION_MISMATCH" in rejected.mismatch_codes
    wrong_anchor = _compatibility_kwargs(kernel_input)
    wrong_anchor["expected_iteration29_root_anchor_file_sha256"] = "9" * 64
    rejected_anchor = compare_certificate_to_legacy_action_v1(
        kernel_input,
        provenance,
        result,
        actual,
        legacy,
        **wrong_anchor,
    )
    assert "EXTERNAL_PROVENANCE_ANCHOR_MISMATCH" in rejected_anchor.mismatch_codes


def test_kernel_adapter_rejects_forged_result_diagnostics() -> None:
    kernel_input = _fixture_kernel_input()
    request = compile_request_from_kernel_input_v1(kernel_input)
    result = _compile(request)
    assert result.certificate is not None
    verification = verify_certificate_v1(
        request,
        result.certificate,
        expected_compiler_source_sha256=COMPILER_SHA,
        verifier_source_sha256=VERIFIER_SHA,
    )
    value = result.model_dump(mode="json")
    value["unresolved_obligation_ids"] = sorted(
        [*value["unresolved_obligation_ids"], "obligation.forged"]
    )
    value["rejected_action_reasons"] = sorted(
        [*value["rejected_action_reasons"], "action.nonexistent:FORGED_REASON"]
    )
    value["result_sha256"] = pace_digest_v1(
        {key: item for key, item in value.items() if key != "result_sha256"}
    )
    forged = PACECompileResult.model_validate_json(canonical_pace_json_bytes_v1(value))
    provenance = build_fixture_provenance_envelope_v1(
        kernel_input=kernel_input,
        iteration29_root_anchor_file_sha256="1" * 64,
        iteration29_source_manifest_file_sha256="2" * 64,
        adapter_source_sha256=_compatibility_kwargs(kernel_input)[
            "expected_adapter_source_sha256"
        ],
    )
    receipt = compare_certificate_to_legacy_action_v1(
        kernel_input,
        provenance,
        forged,
        verification,
        _legacy_action_for_result(kernel_input, result),
        **_compatibility_kwargs(kernel_input),
    )
    assert receipt.compatible is False
    assert "RESULT_RECOMPUTATION_MISMATCH" in receipt.mismatch_codes


def test_kernel_adapter_rejects_self_consistent_alternate_blueprint() -> None:
    expected_input = _fixture_kernel_input()
    value = expected_input.model_dump(mode="json")
    selected_projection = next(
        item
        for item in value["blueprint"]["action_projections"]
        if item["pace_action_id"] == "action.acquire_causation"
    )
    selected_projection["title"] = "Self-consistent but externally unbound title"
    blueprint = value["blueprint"]
    blueprint["blueprint_sha256"] = pace_digest_v1(
        {key: item for key, item in blueprint.items() if key != "blueprint_sha256"}
    )
    value["input_sha256"] = pace_digest_v1(
        {key: item for key, item in value.items() if key != "input_sha256"}
    )
    alternate = PACEKernelInputV1.model_validate_json(
        canonical_pace_json_bytes_v1(value)
    )
    request = compile_request_from_kernel_input_v1(alternate)
    result = _compile(request)
    assert result.certificate is not None
    verification = verify_certificate_v1(
        request,
        result.certificate,
        expected_compiler_source_sha256=COMPILER_SHA,
        verifier_source_sha256=VERIFIER_SHA,
    )
    provenance = build_fixture_provenance_envelope_v1(
        kernel_input=alternate,
        iteration29_root_anchor_file_sha256="1" * 64,
        iteration29_source_manifest_file_sha256="2" * 64,
        adapter_source_sha256=_compatibility_kwargs(alternate)[
            "expected_adapter_source_sha256"
        ],
    )
    receipt = compare_certificate_to_legacy_action_v1(
        alternate,
        provenance,
        result,
        verification,
        _legacy_action_for_result(alternate, result),
        **_compatibility_kwargs(expected_input),
    )
    assert receipt.compatible is False
    assert receipt.mismatch_codes == ("EXTERNAL_KERNEL_INPUT_ANCHOR_MISMATCH",)


def test_kernel_blueprint_rejects_unrelated_fact_projection() -> None:
    value = _fixture_kernel_input().model_dump(mode="json")
    projection = next(
        item
        for item in value["blueprint"]["action_projections"]
        if item["pace_action_id"] == "action.acquire_causation"
    )
    projection["fact_id"] = "claim_timely"
    blueprint = value["blueprint"]
    blueprint["blueprint_sha256"] = pace_digest_v1(
        {key: item for key, item in blueprint.items() if key != "blueprint_sha256"}
    )
    value["input_sha256"] = pace_digest_v1(
        {key: item for key, item in value.items() if key != "input_sha256"}
    )
    with pytest.raises(ValidationError, match="not lossless in the single-fact ABI"):
        PACEKernelInputV1.model_validate_json(canonical_pace_json_bytes_v1(value))


def test_kernel_blueprint_rejects_multi_predicate_obligation_projection() -> None:
    value = _fixture_kernel_input().model_dump(mode="json")
    value["blueprint"]["obligations"][0].update(
        {
            "kind": "DISAMBIGUATE",
            "predicate_ids": ["causation_supported", "claim_timely"],
            "target_atoms": [],
        }
    )
    blueprint = value["blueprint"]
    blueprint["blueprint_sha256"] = pace_digest_v1(
        {key: item for key, item in blueprint.items() if key != "blueprint_sha256"}
    )
    value["input_sha256"] = pace_digest_v1(
        {key: item for key, item in value.items() if key != "input_sha256"}
    )
    with pytest.raises(ValidationError, match="not lossless in the single-fact ABI"):
        PACEKernelInputV1.model_validate_json(canonical_pace_json_bytes_v1(value))


def test_kernel_blueprint_rejects_deadline_obligation_projection() -> None:
    value = _fixture_kernel_input().model_dump(mode="json")
    value["blueprint"]["obligations"][0].update(
        {
            "kind": "SATISFY_DEADLINE",
            "predicate_ids": [],
            "target_atoms": [],
            "deadline": "2026-06-01T00:00:00+00:00",
            "satisfaction_event_types": ["DEADLINE_FILED"],
        }
    )
    blueprint = value["blueprint"]
    blueprint["blueprint_sha256"] = pace_digest_v1(
        {key: item for key, item in blueprint.items() if key != "blueprint_sha256"}
    )
    value["input_sha256"] = pace_digest_v1(
        {key: item for key, item in value.items() if key != "input_sha256"}
    )
    with pytest.raises(ValidationError, match="not lossless in the single-fact ABI"):
        PACEKernelInputV1.model_validate_json(canonical_pace_json_bytes_v1(value))


@pytest.mark.parametrize("side_kind", ["SATISFY_DEADLINE", "DISAMBIGUATE"])
def test_kernel_blueprint_rejects_unaddressed_side_obligation(
    side_kind: str,
) -> None:
    value = _fixture_kernel_input().model_dump(mode="json")
    side = deepcopy(value["blueprint"]["obligations"][0])
    side["obligation_id"] = f"obligation.side.{side_kind.lower()}"
    side["kind"] = side_kind
    side["target_atoms"] = []
    if side_kind == "SATISFY_DEADLINE":
        side["predicate_ids"] = []
        side["deadline"] = "2026-06-01T00:00:00+00:00"
        side["satisfaction_event_types"] = ["DEADLINE_FILED"]
    else:
        side["predicate_ids"] = ["causation_supported", "claim_timely"]
    value["blueprint"]["obligations"].append(side)
    value["blueprint"]["obligations"].sort(key=lambda item: item["obligation_id"])
    children = [
        deepcopy(value["blueprint"]["obligation_expression"]),
        {
            "operator": "OBLIGATION",
            "obligation_id": side["obligation_id"],
            "children": [],
            "condition": None,
            "temporal_at": None,
        },
    ]
    children.sort(key=pace_digest_v1)
    value["blueprint"]["obligation_expression"] = {
        "operator": "ALL_OF",
        "obligation_id": None,
        "children": children,
        "condition": None,
        "temporal_at": None,
    }
    blueprint = value["blueprint"]
    blueprint["blueprint_sha256"] = pace_digest_v1(
        {key: item for key, item in blueprint.items() if key != "blueprint_sha256"}
    )
    value["input_sha256"] = pace_digest_v1(
        {key: item for key, item in value.items() if key != "input_sha256"}
    )
    with pytest.raises(ValidationError, match="complete expression/action coverage"):
        PACEKernelInputV1.model_validate_json(canonical_pace_json_bytes_v1(value))


def test_kernel_blueprint_rejects_duplicate_wrapped_obligation_leaf() -> None:
    value = _fixture_kernel_input().model_dump(mode="json")
    leaf = deepcopy(value["blueprint"]["obligation_expression"])
    wrapped = {
        "operator": "TEMPORAL",
        "obligation_id": None,
        "children": [deepcopy(leaf)],
        "condition": None,
        "temporal_at": "2026-01-01T00:00:00+00:00",
    }
    children = [leaf, wrapped]
    children.sort(key=pace_digest_v1)
    value["blueprint"]["obligation_expression"] = {
        "operator": "ALL_OF",
        "obligation_id": None,
        "children": children,
        "condition": None,
        "temporal_at": None,
    }
    blueprint = value["blueprint"]
    blueprint["blueprint_sha256"] = pace_digest_v1(
        {key: item for key, item in blueprint.items() if key != "blueprint_sha256"}
    )
    value["input_sha256"] = pace_digest_v1(
        {key: item for key, item in value.items() if key != "input_sha256"}
    )
    with pytest.raises(ValidationError, match="complete expression/action coverage"):
        PACEKernelInputV1.model_validate_json(canonical_pace_json_bytes_v1(value))


def _wait_for_run(storage: Storage, run_id: str, session_id: str) -> None:
    for _ in range(500):
        row = storage.get_run(run_id, session_id=session_id)
        if row and row["status"] in {"complete", "failed"}:
            assert row["status"] == "complete", row.get("error")
            return
        time.sleep(0.01)
    raise AssertionError("reference source run timed out")


def test_real_iteration29_state_projection_is_read_only(tmp_path: Path) -> None:
    storage = Storage(str(tmp_path / "pace-kernel-adapter.db"))
    source = ClaimPipeline(storage, model_mode=MODEL_MODE_REFERENCE, pace_seconds=0)
    session_id = "pace-kernel-adapter-session"
    run_id = source.create("DEF-027-E0-DEMO", session_id=session_id)
    _wait_for_run(storage, run_id, session_id)
    cycle = ClaimPipeline(
        storage,
        model_mode=MODEL_MODE_REFERENCE,
        agent_orchestrator=NemotronMultiAgentOrchestrator(
            storage,
            agent_runner=DeterministicStructuredAgent(),
        ),
        pace_seconds=0,
    )
    service = ClaimLoopService(
        storage,
        cycle_pipeline=cycle,
        cycle_transport_mode="deterministic_test_double",
    )
    created = service.create(
        session_id=session_id,
        source_run_id=run_id,
        idempotency_key="pace-adapter-create",
    )
    state = service.state(session_id=session_id, loop_id=created["loop_id"])
    before = canonical_json_bytes(state.model_dump(mode="json"))
    readiness, provenance = project_kernel_state_v1(
        state,
        iteration29_root_anchor_file_sha256="1" * 64,
        iteration29_source_manifest_file_sha256="2" * 64,
        adapter_source_sha256=hashlib.sha256(
            (PACE_ROOT / "kernel_adapter.py").read_bytes()
        ).hexdigest(),
    )
    after = canonical_json_bytes(state.model_dump(mode="json"))
    assert before == after
    assert readiness.classification == "PACE_CORE_ADAPTER_NOT_READY"
    assert readiness.reason_code == "NEUTRAL_BLUEPRINT_UNAVAILABLE"
    assert readiness.request_constructed is False
    assert readiness.compiler_executed is False
    assert readiness.certificate_emitted is False
    assert readiness.kernel_mutated is False
    assert provenance.blueprint_sha256 is None
    assert provenance.snapshot_sha256 is None
    assert provenance.kernel_input_sha256 is None


def test_accepted_kernel_sources_do_not_import_pace() -> None:
    kernel_sources = (
        ROOT / "casepath_api" / "claim_loop.py",
        ROOT / "casepath_api" / "claim_loop_contracts.py",
        ROOT / "casepath_api" / "claim_loop_cycle.py",
        ROOT / "casepath_api" / "claim_loop_service.py",
        ROOT / "casepath_api" / "claim_loop_store.py",
    )
    for path in kernel_sources:
        tree = ast.parse(path.read_text())
        imports = [
            node.module or ""
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        ]
        imports.extend(
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        )
        assert all("pace" not in value for value in imports)
