from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import threading
import time

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from casepath_api.canonicalizer import MODEL_MODE_REFERENCE
from casepath_api.claim_loop import DeterministicMouldArtifactInterpreter
from casepath_api.claim_loop_contracts import EvidenceAction
from casepath_api.claim_loop_router import create_claim_loop_router
from casepath_api.claim_loop_service import (
    ClaimLoopService,
    ClaimLoopServiceError,
    _protocol_records_with,
)
from casepath_api.claim_loop_store import ClaimLoopStoreError
from casepath_api.foundation.common import (
    canonical_json_bytes,
    digest_text,
    digest_value,
)
from casepath_api.insurance_protocol_v1 import InsuranceProtocolRecordSetV1
from casepath_api.insurance_protocol_v2 import InsuranceThinWaistRecordSetV2
from casepath_api.insurance_pace_bridge_v1 import (
    build_neutral_assessment_request_v1,
    pace_current_decision_scope_v1,
    validate_claim_derived_pace_request_v1,
)
from casepath_api.insurance_correction_v1 import (
    MouldNeutralAssessmentCorrectionAdapterV1,
    MouldNeutralAssessmentRollbackAdapterV1,
)
from casepath_api.ecab_registry_adapter_v1 import (
    ECABFactualHistoryRegistryAdapterV1,
)
from casepath_api.ecab_replay_adapter import (
    build_ecab_factual_history_span_v1,
)
from casepath_api.local_artifact_registry import (
    LocalArtifactRegistryAdapterV1,
    LocalArtifactRegistryError,
    LocalRegistryMaterialV1,
)
from casepath_api.multi_agent import (
    DeterministicStructuredAgent,
    InstrumentedStructuredAgent,
    NemotronMultiAgentOrchestrator,
)
from casepath_api import multi_agent as multi_agent_module
from casepath_api.pipeline_v15 import ClaimPipeline
from casepath_api.storage import Storage


SESSION = "insurance-protocol-test-session-0001"
CLAIM_ID = "DEF-027-E0-DEMO"
NEUTRAL_ASSESSMENT = canonical_json_bytes(
    {
        "schema": "casepath.synthetic-neutral-assessment/1.0.0",
        "document_kind": "neutral_assessment",
        "evidence_item_id": "technical_assessment",
        "finding": "building",
        "basis": (
            "Synthetic technical inspection records a building-related cause "
            "for this public development fixture."
        ),
    }
).decode("utf-8")


def _typed_assessment(
    *,
    finding: str = "building",
    basis: str = "A distinct handler-authored factual basis.",
    evidence_item_id: str = "technical_assessment",
) -> str:
    return canonical_json_bytes(
        {
            "schema": "casepath.synthetic-neutral-assessment/1.0.0",
            "document_kind": "neutral_assessment",
            "evidence_item_id": evidence_item_id,
            "finding": finding,
            "basis": basis,
        }
    ).decode("utf-8")


class ManualClock:
    def __init__(self) -> None:
        self._value = datetime(2026, 8, 28, 12, 0, tzinfo=timezone.utc)
        self._lock = threading.Lock()

    def __call__(self) -> str:
        with self._lock:
            value = self._value
            self._value += timedelta(milliseconds=1)
        return value.isoformat()

    def advance(self, seconds: int) -> None:
        with self._lock:
            self._value += timedelta(seconds=seconds)


class FaultOnce:
    def __init__(self, phase: str, *, action=None) -> None:
        self.phase = phase
        self.action = action
        self.fired = False

    def __call__(self, phase: str) -> None:
        if phase != self.phase or self.fired:
            return
        self.fired = True
        if self.action is not None:
            self.action()
            return
        raise RuntimeError(f"injected {phase}")


class SimulatedProcessDeath(BaseException):
    """Fatal test interruption that ordinary service error handling cannot catch."""


def _kill_process() -> None:
    raise SimulatedProcessDeath("simulated process death")


def _wait(storage: Storage, run_id: str) -> dict[str, object]:
    for _ in range(500):
        run = storage.get_run(run_id, session_id=SESSION)
        if run is not None and run["status"] in {"complete", "failed"}:
            assert run["status"] == "complete", run.get("error")
            return run
        time.sleep(0.01)
    raise AssertionError("source run did not complete")


def _cycle_pipeline(storage: Storage) -> ClaimPipeline:
    return ClaimPipeline(
        storage,
        model_mode=MODEL_MODE_REFERENCE,
        agent_orchestrator=NemotronMultiAgentOrchestrator(
            storage,
            agent_runner=DeterministicStructuredAgent(),
        ),
        pace_seconds=0,
    )


def _service_fixture(
    tmp_path: Path,
    *,
    registry_fault=None,
    service_fault=None,
    registry_class=LocalArtifactRegistryAdapterV1,
) -> tuple[
    Storage,
    ClaimLoopService,
    LocalArtifactRegistryAdapterV1,
    str,
    ManualClock,
]:
    storage = Storage(str(tmp_path / "casepath.db"))
    source = ClaimPipeline(
        storage,
        model_mode=MODEL_MODE_REFERENCE,
        pace_seconds=0,
    )
    run_id = source.create(CLAIM_ID, session_id=SESSION)
    _wait(storage, run_id)
    registry = registry_class(tmp_path / "artifact-registry", fault_hook=registry_fault)
    clock = ManualClock()
    service = ClaimLoopService(
        storage,
        artifact_interpreter=DeterministicMouldArtifactInterpreter(),
        cycle_pipeline=_cycle_pipeline(storage),
        cycle_transport_mode="deterministic_test_double",
        source_pipeline=_cycle_pipeline(storage),
        protocol_adapter=registry,
        correction_adapters={
            MouldNeutralAssessmentCorrectionAdapterV1.adapter_id: (
                MouldNeutralAssessmentCorrectionAdapterV1()
            ),
            MouldNeutralAssessmentRollbackAdapterV1.adapter_id: (
                MouldNeutralAssessmentRollbackAdapterV1()
            ),
        },
        protocol_fault_hook=service_fault,
        clock=clock,
    )
    created = service.create(
        session_id=SESSION,
        source_run_id=run_id,
        idempotency_key="create-insurance-loop-0001",
    )
    return storage, service, registry, created["loop_id"], clock


def _recreate_service(
    *,
    storage: Storage,
    registry: LocalArtifactRegistryAdapterV1,
    clock: ManualClock,
) -> ClaimLoopService:
    return ClaimLoopService(
        storage,
        artifact_interpreter=DeterministicMouldArtifactInterpreter(),
        cycle_pipeline=_cycle_pipeline(storage),
        cycle_transport_mode="deterministic_test_double",
        source_pipeline=_cycle_pipeline(storage),
        protocol_adapter=registry,
        correction_adapters={
            MouldNeutralAssessmentCorrectionAdapterV1.adapter_id: (
                MouldNeutralAssessmentCorrectionAdapterV1()
            ),
            MouldNeutralAssessmentRollbackAdapterV1.adapter_id: (
                MouldNeutralAssessmentRollbackAdapterV1()
            ),
        },
        clock=clock,
    )


def _prepare_registration(tmp_path: Path, **kwargs):
    storage, service, registry, loop_id, clock = _service_fixture(tmp_path, **kwargs)
    proposal = service.protocol_proposal(session_id=SESSION, loop_id=loop_id)
    staged = service.stage_protocol_material(
        session_id=SESSION,
        loop_id=loop_id,
        filename="neutral-assessment.txt",
        media_type="text/plain; charset=utf-8",
        content=NEUTRAL_ASSESSMENT,
        idempotency_key="stage-neutral-assessment-0001",
        expected_revision=proposal["revision"],
    )
    return storage, service, registry, loop_id, clock, proposal, staged


def _prepare_ecab_registration(tmp_path: Path, **kwargs):
    storage, service, registry, loop_id, clock = _service_fixture(
        tmp_path,
        registry_class=ECABFactualHistoryRegistryAdapterV1,
        **kwargs,
    )
    proposal = service.protocol_proposal(session_id=SESSION, loop_id=loop_id)
    action = EvidenceAction.model_validate(proposal["registration_action"])
    state = service.state(session_id=SESSION, loop_id=loop_id)
    page = "Outcome-free factual history. " + NEUTRAL_ASSESSMENT + " End."
    start = page.index(NEUTRAL_ASSESSMENT)
    end = start + len(NEUTRAL_ASSESSMENT)
    span = build_ecab_factual_history_span_v1(
        event_index=0,
        previous_event_sha256=None,
        action_id=action.action_id,
        action_sha256=action.action_sha256,
        source_id="source.synthetic-factual-history-0001",
        source_sha256=digest_text(page),
        source_version=state.record_version,
        page=1,
        sanitized_page_text=page,
        text_start=start,
        text_end=end,
        observed_at="2026-08-28T11:59:00+00:00",
    )
    staged = service.stage_protocol_factual_history(
        session_id=SESSION,
        loop_id=loop_id,
        span=span,
        idempotency_key="stage-factual-history-0001",
        expected_revision=proposal["revision"],
    )
    return storage, service, registry, loop_id, clock, proposal, staged, span


def _register(service, loop_id, proposal, staged):
    return service.register_protocol_material(
        session_id=SESSION,
        loop_id=loop_id,
        proposal_sha256=proposal["proposal_sha256"],
        staged_artifact_receipt_sha256=(staged["staged_artifact_receipt_sha256"]),
        idempotency_key="register-neutral-assessment-0001",
        expected_revision=proposal["revision"],
    )


def _rehash_thin_waist(value: dict[str, object]) -> dict[str, object]:
    """Rehash a deliberately modified V2 chain in predecessor order."""

    assertion = value["normalized_assertion"]
    assert isinstance(assertion, dict)
    assertion["assertion_sha256"] = digest_value(
        {key: item for key, item in assertion.items() if key != "assertion_sha256"}
    )
    interpretation = value["interpretation"]
    assert isinstance(interpretation, dict)
    interpretation["assertion_sha256"] = assertion["assertion_sha256"]
    interpretation["interpretation_sha256"] = digest_value(
        {
            key: item
            for key, item in interpretation.items()
            if key != "interpretation_sha256"
        }
    )
    proposal = value["decision_proposal"]
    assert isinstance(proposal, dict)
    proposal["normalized_assertion_sha256"] = assertion["assertion_sha256"]
    proposal["interpretation_sha256"] = interpretation["interpretation_sha256"]
    proposal["proposal_sha256"] = digest_value(
        {key: item for key, item in proposal.items() if key != "proposal_sha256"}
    )
    decision = value["decision_record"]
    assert isinstance(decision, dict)
    decision["proposal_sha256"] = proposal["proposal_sha256"]
    decision["interpretation_sha256"] = interpretation["interpretation_sha256"]
    decision["decision_sha256"] = digest_value(
        {key: item for key, item in decision.items() if key != "decision_sha256"}
    )
    intent = value["action_intent"]
    assert isinstance(intent, dict)
    intent["proposal_sha256"] = proposal["proposal_sha256"]
    intent["decision_sha256"] = decision["decision_sha256"]
    intent["interpretation_sha256"] = interpretation["interpretation_sha256"]
    intent["intent_sha256"] = digest_value(
        {key: item for key, item in intent.items() if key != "intent_sha256"}
    )
    action_receipt = value.get("action_receipt")
    if isinstance(action_receipt, dict):
        action_receipt["intent_sha256"] = intent["intent_sha256"]
        action_receipt["receipt_sha256"] = digest_value(
            {
                key: item
                for key, item in action_receipt.items()
                if key != "receipt_sha256"
            }
        )
    value["record_set_sha256"] = digest_value(
        {key: item for key, item in value.items() if key != "record_set_sha256"}
    )
    return value


def _pending_observation_append(tmp_path: Path):
    fault = FaultOnce("AFTER_INTERPRETATION")
    _, service, _, loop_id, _, proposal, staged = _prepare_registration(
        tmp_path, service_fault=fault
    )
    with pytest.raises(RuntimeError, match="AFTER_INTERPRETATION"):
        _register(service, loop_id, proposal, staged)
    state, events = service.store.snapshot(session_id=SESSION, loop_id=loop_id)
    protocol_entries = service._protocol_entries(events)
    prior_event, records = protocol_entries[-1]
    origin_event = protocol_entries[0][0]
    request_sha256 = origin_event.command["client_request_sha256"]
    client_key = origin_event.command["client_idempotency_key"]
    artifact = service.store.tool_artifact_for_dispatch(
        session_id=SESSION,
        loop_id=loop_id,
        dispatch_sha256=state.active_dispatch_sha256,
    )
    assert artifact is not None
    assert records.source_observation is not None
    lineage = service._thin_waist_replan_intent_v2(
        state=state,
        records=records,
        timestamp=records.source_observation.observed_at,
    )
    command = service._observation_command(state=state, artifact=artifact)
    command.update(
        {
            "client_request_type": "insurance_register",
            "client_request_sha256": request_sha256,
            "client_idempotency_key": client_key,
            "protocol_record_set_sha256": records.record_set_sha256,
            "insurance_protocol_v1": records.model_dump(mode="json"),
            "thin_waist_record_set_sha256": lineage.record_set_sha256,
            "insurance_thin_waist_v2": lineage.model_dump(mode="json"),
            "prior_protocol_event_sha256": prior_event.event_sha256,
        }
    )
    result_key = service._internal_event_key(
        session_id=SESSION,
        loop_id=loop_id,
        client_idempotency_key=client_key,
        request_sha256=request_sha256,
        request_type="insurance_register",
        event_kind="result",
    )
    return service, loop_id, state, records, command, result_key


def test_protocol_clean_registration_replans_same_graph(tmp_path: Path) -> None:
    storage, service, registry, loop_id, _, proposal, staged = _prepare_registration(
        tmp_path
    )
    result = _register(service, loop_id, proposal, staged)

    protocol = result["protocol_state"]
    assert protocol["protocol_status"] == "replanned"
    assert protocol["contract"] == "casepath.versioned-case-state/2.0.0"
    assert protocol["pending_intent_sha256"] is None
    thin = InsuranceThinWaistRecordSetV2.model_validate(
        protocol["thin_waist_record_set"]
    )
    assert thin.action_receipt is not None
    assert (
        thin.normalized_assertion.source_observation_sha256
        == thin.source_observation.observation_sha256
    )
    assert (
        thin.interpretation.assertion_sha256
        == thin.normalized_assertion.assertion_sha256
    )
    assert (
        thin.decision_proposal.interpretation_sha256
        == thin.interpretation.interpretation_sha256
    )
    assert (
        thin.decision_record.proposal_sha256 == thin.decision_proposal.proposal_sha256
    )
    assert thin.action_intent.decision_sha256 == thin.decision_record.decision_sha256
    assert thin.action_receipt.intent_sha256 == thin.action_intent.intent_sha256
    for record, hash_field in (
        (thin.source_observation, "observation_sha256"),
        (thin.normalized_assertion, "assertion_sha256"),
        (thin.interpretation, "interpretation_sha256"),
        (thin.decision_proposal, "proposal_sha256"),
        (thin.decision_record, "decision_sha256"),
        (thin.action_intent, "intent_sha256"),
        (thin.action_receipt, "receipt_sha256"),
    ):
        assert getattr(record, hash_field) == digest_value(
            record.model_dump(mode="json", exclude={hash_field})
        )
    assert thin.record_set_sha256 == digest_value(
        thin.model_dump(mode="json", exclude={"record_set_sha256"})
    )
    events = service.store.events(session_id=SESSION, loop_id=loop_id)
    assert events[-2].event_type == "OBSERVATION_INGESTED"
    assert events[-1].event_type == "PROTOCOL_REPLAN_RECEIPT_RECORDED"
    assert tuple(protocol["protocol_event_sha256s"])[-2:] == (
        events[-2].event_sha256,
        events[-1].event_sha256,
    )
    assert registry.effect_count() == 1
    audit = service.audit(session_id=SESSION, loop_id=loop_id)
    assert audit["incremental_loop_activity"]["model_calls"] == 0
    assert audit["incremental_loop_activity"]["provider_calls"] == 0
    assert audit["incremental_loop_activity"]["cost_usd"] == 0.0
    assert storage.model_calls() == []


def test_pace_request_is_exactly_claim_derived_without_invariant_fixture_ids(
    tmp_path: Path,
) -> None:
    _, service, _, loop_id, _, _, _ = _prepare_registration(tmp_path)
    state = service.state(session_id=SESSION, loop_id=loop_id)
    events = service.store.events(session_id=SESSION, loop_id=loop_id)
    tail = events[-1]
    request = build_neutral_assessment_request_v1(
        state=state, journal_events=events
    )
    proposal_before_selection = service.protocol_proposal(
        session_id=SESSION, loop_id=loop_id
    )
    wire = request.model_dump(mode="json")
    encoded = canonical_json_bytes(wire).decode("utf-8")
    forbidden = (
        "SYNTHETIC-PACE-INVARIANT",
        "action.orphan",
        "claim_timely",
        "evidence.causation_support",
        "inactive_future_node",
        "locator.causation_section",
        "locator.timeliness_field",
        "pace-fixture",
        "source.medical_record",
        "1111111111111111111111111111111111111111111111111111111111111111",
    )
    assert all(value not in encoded for value in forbidden)

    process_nodes = {value["node_id"] for value in state.process["nodes"]}
    process_edges = {
        (value["source"], value["target"])
        for value in state.process["edges"]
        if value["state"] != "loop"
    }
    current_node = next(
        value
        for value in state.process["nodes"]
        if value["node_id"] == state.process["current_overlay"]["current_node_id"]
    )
    process_branches = {value["branch_id"] for value in current_node["branches"]}
    assert {value.node_id for value in request.state.graph.nodes}.issubset(process_nodes)
    assert {
        (value.source_node_id, value.target_node_id)
        for value in request.state.graph.edges
    }.issubset(process_edges)
    assert {value.branch_id for value in request.state.graph.branches}.issubset(
        process_branches
    )

    item = next(
        value
        for value in state.checklist["items"]
        if value["item_id"] == "technical_assessment"
    )
    assert len(request.state.sources) == 1
    source = request.state.sources[0]
    template_record = state.accepted_artifacts["playbook_template_record"]
    assert source.source_id == template_record["template"]["template_id"]
    assert source.source_id != item["item_id"]
    assert source.source_sha256 == template_record["template"]["template_sha256"]
    assert source.locator_ids[0].startswith("locator.capability.")
    assert request.state.documents[0].evidence_item_id == item["item_id"]
    assert request.state.documents[0].source_ids == ()
    assert request.actions[0].evidence_item_id == item["item_id"]
    assert request.actions[0].process_node_id == current_node["node_id"]
    assert request.actions[0].source_ids == (source.source_id,)
    assert request.actions[0].locator_ids == source.locator_ids
    assert request.actions[0].action_id == "evidence.obtain_neutral_assessment@1"
    assert {value.outcome_id for value in request.actions[0].outcomes} == {
        "outcome.causation.building",
        "outcome.causation.mixed",
        "outcome.causation.tenant_use",
        "outcome.causation.unresolved",
    }
    assert {
        value.predicate_id for value in request.state.graph.predicate_specs
    } == {
        "decision.causation.is.building",
        "decision.causation.is.mixed",
        "decision.causation.is.tenant_use",
    }
    assert len(request.state.graph.constraints[0].condition.clauses) == 4
    assert request.state.graph.knowledge_version.endswith(
        template_record["template"]["template_sha256"]
    )
    assert state.state_sha256 not in request.state.graph.knowledge_version
    scope = pace_current_decision_scope_v1(state=state, journal_events=events)
    assert scope["certificate_scope"] == (
        "CURRENT_DECISION_SLICE_NOT_GLOBAL_NEXT_ACTION"
    )
    assert scope["global_scheduler_authority"] == "CLAIM_LOOP_ONLY"
    assert scope["earlier_mandatory_obligation_ids"] == [
        "recurrence_chronology"
    ]

    forged_source = request.state.sources[0].model_copy(
        update={"source_id": item["item_id"]}
    )
    forged_state = request.state.model_copy(update={"sources": (forged_source,)})
    forged_request = request.model_copy(update={"state": forged_state})
    with pytest.raises(ValueError, match="request is not the exact claim-derived"):
        validate_claim_derived_pace_request_v1(
            state=state,
            journal_events=events,
            request=forged_request,
        )

    wrong_tail = tail.model_copy(update={"sequence": tail.sequence + 1})
    with pytest.raises(ValueError, match="journal prefix"):
        build_neutral_assessment_request_v1(
            state=state,
            journal_events=(*events[:-1], wrong_tail),
        )

    service.select_action(
        session_id=SESSION,
        loop_id=loop_id,
        idempotency_key="pace-selected-action-invariance-0001",
        expected_revision=state.revision,
    )
    selected_state = service.state(session_id=SESSION, loop_id=loop_id)
    selected_events = service.store.events(session_id=SESSION, loop_id=loop_id)
    selected_request = build_neutral_assessment_request_v1(
        state=selected_state,
        journal_events=selected_events,
    )
    proposal_after_selection = service.protocol_proposal(
        session_id=SESSION, loop_id=loop_id
    )
    assert selected_request == request
    assert selected_state.state_sha256 != state.state_sha256
    assert (
        proposal_after_selection["proposal"]["pace_request"]
        == proposal_before_selection["proposal"]["pace_request"]
    )
    assert (
        proposal_after_selection["proposal_sha256"]
        != proposal_before_selection["proposal_sha256"]
    )
    assert (
        proposal_after_selection["proposal"]["source_state_sha256"]
        == selected_state.state_sha256
    )


@pytest.mark.parametrize(
    ("section", "field", "replacement"),
    (
        ("normalized_assertion", "extraction_method", "forged.extractor/9"),
        ("interpretation", "policy_version", "forged.policy/9"),
        ("interpretation", "status", "disputed"),
        ("decision_proposal", "session_id", "forged-session-0001"),
    ),
)
def test_v2_rehashed_semantic_tamper_rejected_before_append(
    tmp_path: Path,
    section: str,
    field: str,
    replacement: str,
) -> None:
    service, loop_id, state, records, command, result_key = _pending_observation_append(
        tmp_path
    )
    forged = json.loads(canonical_json_bytes(command["insurance_thin_waist_v2"]))
    forged[section][field] = replacement
    forged = _rehash_thin_waist(forged)
    command["insurance_thin_waist_v2"] = forged
    command["thin_waist_record_set_sha256"] = forged["record_set_sha256"]
    before_events = service.store.events(session_id=SESSION, loop_id=loop_id)
    before_state = service.state(session_id=SESSION, loop_id=loop_id)
    with pytest.raises(ClaimLoopStoreError):
        service.store.append(
            session_id=SESSION,
            loop_id=loop_id,
            event_type="OBSERVATION_INGESTED",
            idempotency_key=result_key,
            command=command,
            timestamp=records.source_observation.observed_at,
            expected_revision=state.revision,
        )
    after_events = service.store.events(session_id=SESSION, loop_id=loop_id)
    after_state = service.state(session_id=SESSION, loop_id=loop_id)
    assert after_events == before_events
    assert after_state.state_sha256 == before_state.state_sha256


@pytest.mark.parametrize(
    ("fault_phase", "event_type", "event_kind"),
    (
        (
            "BEFORE_SOURCE_OBSERVATION",
            "PROTOCOL_SOURCE_OBSERVATION_RECORDED",
            "source-observation",
        ),
        (
            "BEFORE_NORMALIZED_ASSERTION",
            "PROTOCOL_ASSERTION_NORMALIZED",
            "normalized-assertion",
        ),
        (
            "BEFORE_INTERPRETATION",
            "PROTOCOL_INTERPRETATION_RECORDED",
            "interpretation",
        ),
    ),
)
def test_epistemic_stage_rehashed_tamper_rejected_before_journal_growth(
    tmp_path: Path,
    fault_phase: str,
    event_type: str,
    event_kind: str,
) -> None:
    fault = FaultOnce(fault_phase)
    _, service, registry, loop_id, _, proposal, staged = _prepare_registration(
        tmp_path, service_fault=fault
    )
    with pytest.raises(RuntimeError, match=fault_phase):
        _register(service, loop_id, proposal, staged)
    state, events = service.store.snapshot(session_id=SESSION, loop_id=loop_id)
    records = service._protocol_entries(events)[-1][1]
    artifact = service.store.tool_artifact_for_dispatch(
        session_id=SESSION,
        loop_id=loop_id,
        dispatch_sha256=state.active_dispatch_sha256,
    )
    assert artifact is not None
    assert records.action_receipt is not None
    if event_type == "PROTOCOL_SOURCE_OBSERVATION_RECORDED":
        source = service._source_observation(
            state=state,
            records=records,
            receipt=records.action_receipt,
            content=registry.content(records.staged_artifact),
        )
        source_payload = source.model_dump(mode="json", exclude={"observation_sha256"})
        source_payload["observed_at"] = (
            datetime.fromisoformat(source.observed_at) + timedelta(milliseconds=1)
        ).isoformat()
        forged_records = _protocol_records_with(
            records,
            source_observation={
                **source_payload,
                "observation_sha256": digest_value(source_payload),
            },
        )
        event_timestamp = source.observed_at
    elif event_type == "PROTOCOL_ASSERTION_NORMALIZED":
        assert records.source_observation is not None
        assertion = service._normalized_assertion(
            source=records.source_observation,
            artifact=artifact,
        )
        assertion_payload = assertion.model_dump(
            mode="json", exclude={"assertion_sha256"}
        )
        assertion_payload["extraction_method"] = "forged.extractor/9"
        forged_records = _protocol_records_with(
            records,
            normalized_assertion={
                **assertion_payload,
                "assertion_sha256": digest_value(assertion_payload),
            },
        )
        event_timestamp = records.source_observation.observed_at
    else:
        assert records.source_observation is not None
        assert records.normalized_assertion is not None
        interpretation = service._interpretation_record(
            state=state,
            assertion=records.normalized_assertion,
        )
        interpretation_payload = interpretation.model_dump(
            mode="json", exclude={"interpretation_sha256"}
        )
        interpretation_payload["policy_version"] = "forged.policy/9"
        forged_records = _protocol_records_with(
            records,
            interpretation={
                **interpretation_payload,
                "interpretation_sha256": digest_value(interpretation_payload),
            },
        )
        event_timestamp = records.source_observation.observed_at
    before_events = service.store.events(session_id=SESSION, loop_id=loop_id)
    before_state = service.state(session_id=SESSION, loop_id=loop_id)
    origin = service._protocol_entries(before_events)[0][0]
    with pytest.raises(ClaimLoopServiceError):
        service._append_protocol_event(
            state=state,
            records=forged_records,
            event_type=event_type,
            event_kind=event_kind,
            client_idempotency_key=origin.command["client_idempotency_key"],
            request_sha256=origin.command["client_request_sha256"],
            timestamp=event_timestamp,
        )
    after_events = service.store.events(session_id=SESSION, loop_id=loop_id)
    after_state = service.state(session_id=SESSION, loop_id=loop_id)
    assert after_events == before_events
    assert after_state.state_sha256 == before_state.state_sha256


def test_fault_02_duplicate_registration_replays_exact_result(tmp_path: Path) -> None:
    _, service, registry, loop_id, _, proposal, staged = _prepare_registration(tmp_path)
    first = _register(service, loop_id, proposal, staged)
    second = _register(service, loop_id, proposal, staged)
    assert canonical_json_bytes(second) == canonical_json_bytes(first)
    assert registry.effect_count() == 1


def test_fault_03_duplicate_execute_after_receipt_has_one_effect(
    tmp_path: Path,
) -> None:
    _, service, registry, loop_id, _, proposal, staged = _prepare_registration(tmp_path)
    result = _register(service, loop_id, proposal, staged)
    records = InsuranceProtocolRecordSetV1.model_validate_json(
        canonical_json_bytes(result["protocol_state"]["record_set"])
    )
    receipt = registry.execute(
        intent=records.intent,
        staged=records.staged_artifact,
        executed_at=records.action_receipt.committed_at,
    )
    assert receipt == records.action_receipt
    assert registry.effect_count() == 1


def test_fault_04_same_bytes_new_filename_deduplicates_content(
    tmp_path: Path,
) -> None:
    _, service, registry, loop_id, clock = _service_fixture(tmp_path)
    state = service.state(session_id=SESSION, loop_id=loop_id)
    common = {
        "session_id": SESSION,
        "loop_id": loop_id,
        "claim_id": state.claim_id,
        "record_version": state.record_version,
        "staged_at": clock(),
    }
    first = registry.stage(
        **common,
        material=LocalRegistryMaterialV1(
            filename="assessment-a.txt",
            media_type="text/plain; charset=utf-8",
            content=NEUTRAL_ASSESSMENT,
            claimed_content_sha256=digest_text(NEUTRAL_ASSESSMENT),
        ),
    )
    second = registry.stage(
        **{**common, "staged_at": clock()},
        material=LocalRegistryMaterialV1(
            filename="assessment-b.txt",
            media_type="text/plain; charset=utf-8",
            content=NEUTRAL_ASSESSMENT,
            claimed_content_sha256=digest_text(NEUTRAL_ASSESSMENT),
        ),
    )
    assert first.receipt_sha256 != second.receipt_sha256
    assert first.content_sha256 == second.content_sha256
    assert registry.content_blob_count() == 0
    assert len(tuple(registry.quarantine_root.glob("*.txt"))) == 1


def test_faults_05_06_invalid_type_and_hash_fail_before_quarantine(
    tmp_path: Path,
) -> None:
    _, service, registry, loop_id, clock = _service_fixture(tmp_path)
    state = service.state(session_id=SESSION, loop_id=loop_id)
    common = {
        "session_id": SESSION,
        "loop_id": loop_id,
        "claim_id": state.claim_id,
        "record_version": state.record_version,
        "staged_at": clock(),
    }
    with pytest.raises(LocalArtifactRegistryError, match="UNSUPPORTED_MEDIA_TYPE"):
        registry.stage(
            **common,
            material=LocalRegistryMaterialV1(
                filename="assessment.pdf",
                media_type="application/pdf",
                content=NEUTRAL_ASSESSMENT,
                claimed_content_sha256=digest_text(NEUTRAL_ASSESSMENT),
            ),
        )
    with pytest.raises(LocalArtifactRegistryError, match="CONTENT_HASH_MISMATCH"):
        registry.stage(
            **common,
            material=LocalRegistryMaterialV1(
                filename="assessment.txt",
                media_type="text/plain; charset=utf-8",
                content=NEUTRAL_ASSESSMENT,
                claimed_content_sha256="0" * 64,
            ),
        )
    assert not tuple(registry.quarantine_root.glob("*.txt"))


def test_typed_evidence_admission_is_closed_and_terminal_before_quarantine(
    tmp_path: Path,
) -> None:
    _, service, registry, loop_id, _ = _service_fixture(tmp_path)
    proposal = service.protocol_proposal(session_id=SESSION, loop_id=loop_id)
    invalid_documents = (
        "{",
        NEUTRAL_ASSESSMENT[:-1] + ',"extra":"forbidden"}',
        (
            '{"schema":"casepath.synthetic-neutral-assessment/1.0.0",'
            '"schema":"casepath.synthetic-neutral-assessment/1.0.0",'
            '"document_kind":"neutral_assessment",'
            '"evidence_item_id":"technical_assessment",'
            '"finding":"building","basis":"duplicate"}'
        ),
        _typed_assessment(evidence_item_id="recurrence_chronology"),
        _typed_assessment(finding="oracle_only_value"),
        _typed_assessment(basis="not NFC: e\u0301"),
        "[" * 20_000 + "0" + "]" * 20_000,
    )
    for index, document in enumerate(invalid_documents, start=1):
        key = f"stage-invalid-typed-assessment-{index:04d}"
        errors = []
        for _ in range(2):
            with pytest.raises(ClaimLoopServiceError) as captured:
                service.stage_protocol_material(
                    session_id=SESSION,
                    loop_id=loop_id,
                    filename="assessment.txt",
                    media_type="text/plain; charset=utf-8",
                    content=document,
                    idempotency_key=key,
                    claimed_content_sha256=digest_text(document),
                    expected_revision=proposal["revision"],
                )
            errors.append(str(captured.value))
        assert errors[0] == errors[1]
    with service.store.connect() as connection:
        rows = connection.execute(
            """SELECT status FROM claim_loop_client_requests
            WHERE session_id=? AND loop_id=? AND request_type='insurance_stage'
            ORDER BY idempotency_key""",
            (SESSION, loop_id),
        ).fetchall()
    assert [row["status"] for row in rows] == ["SUPERSEDED"] * len(
        invalid_documents
    )
    assert registry.effect_count() == 0
    assert not tuple(registry.quarantine_root.glob("*.txt"))
    assert service.state(session_id=SESSION, loop_id=loop_id).revision == proposal[
        "revision"
    ]


def test_distinct_valid_documents_are_server_admitted_and_unresolved_is_not_ready(
    tmp_path: Path,
) -> None:
    _, service, registry, loop_id, _ = _service_fixture(tmp_path)
    proposal = service.protocol_proposal(session_id=SESSION, loop_id=loop_id)
    first_document = _typed_assessment(basis="First independent factual basis.")
    second_document = _typed_assessment(basis="Second independent factual basis.")
    staged = []
    for index, document in enumerate((first_document, second_document), start=1):
        staged.append(
            service.stage_protocol_material(
                session_id=SESSION,
                loop_id=loop_id,
                filename=f"assessment-{index}.txt",
                media_type="text/plain; charset=utf-8",
                content=document,
                idempotency_key=f"stage-distinct-valid-{index:04d}",
                claimed_content_sha256=digest_text(document),
                expected_revision=proposal["revision"],
            )
        )
    assert staged[0]["staged_artifact"]["content_sha256"] != staged[1][
        "staged_artifact"
    ]["content_sha256"]
    assert registry.effect_count() == 0

    unresolved_root = tmp_path / "unresolved"
    unresolved_root.mkdir()
    _, unresolved_service, unresolved_registry, unresolved_loop, _ = (
        _service_fixture(unresolved_root)
    )
    unresolved_proposal = unresolved_service.protocol_proposal(
        session_id=SESSION, loop_id=unresolved_loop
    )
    unresolved_document = _typed_assessment(finding="unresolved")
    unresolved_stage = unresolved_service.stage_protocol_material(
        session_id=SESSION,
        loop_id=unresolved_loop,
        filename="unresolved-assessment.txt",
        media_type="text/plain; charset=utf-8",
        content=unresolved_document,
        idempotency_key="stage-unresolved-assessment-0001",
        claimed_content_sha256=digest_text(unresolved_document),
        expected_revision=unresolved_proposal["revision"],
    )
    result = unresolved_service.register_protocol_material(
        session_id=SESSION,
        loop_id=unresolved_loop,
        proposal_sha256=unresolved_proposal["proposal_sha256"],
        staged_artifact_receipt_sha256=unresolved_stage[
            "staged_artifact_receipt_sha256"
        ],
        idempotency_key="register-unresolved-assessment-0001",
        expected_revision=unresolved_proposal["revision"],
    )
    state = unresolved_service.state(session_id=SESSION, loop_id=unresolved_loop)
    protocol = result["protocol_state"]
    controlling = next(value for value in state.facts if value["fact_id"] == "fact_cause")
    assert controlling["state"] == "unknown"
    assert state.terminal_mode is None
    assert state.phase.value == "awaiting_observation"
    assert protocol["protocol_status"] == "replanned"
    assert protocol["decision_ready_packet_sha256"] is None
    assert protocol["next_action"] == state.selected_action.model_dump(mode="json")
    assert protocol["next_action"]["evidence_item_id"] == "recurrence_chronology"
    assert unresolved_registry.effect_count() == 1


def test_faults_07_08_stale_revision_and_proposal_have_no_effect(
    tmp_path: Path,
) -> None:
    _, service, registry, loop_id, _, proposal, staged = _prepare_registration(tmp_path)
    before = service.state(session_id=SESSION, loop_id=loop_id)
    cases = (
        (
            "stale-revision-registration-0001",
            proposal["proposal_sha256"],
            proposal["revision"] + 1,
            "reservation prefix changed",
        ),
        (
            "stale-proposal-registration-0001",
            "0" * 64,
            proposal["revision"],
            "stale or substituted",
        ),
    )
    for key, proposal_sha256, revision, expected in cases:
        errors = []
        for _ in range(2):
            with pytest.raises(ClaimLoopServiceError, match=expected) as captured:
                service.register_protocol_material(
                    session_id=SESSION,
                    loop_id=loop_id,
                    proposal_sha256=proposal_sha256,
                    staged_artifact_receipt_sha256=(
                        staged["staged_artifact_receipt_sha256"]
                    ),
                    idempotency_key=key,
                    expected_revision=revision,
                )
            errors.append(str(captured.value))
        assert errors[0] == errors[1]
    after = service.state(session_id=SESSION, loop_id=loop_id)
    assert after.state_sha256 == before.state_sha256
    assert registry.effect_count() == 0
    with service.store.connect() as connection:
        rows = connection.execute(
            """SELECT status FROM claim_loop_client_requests
            WHERE session_id=? AND loop_id=? AND request_type='insurance_register'
            ORDER BY idempotency_key""",
            (SESSION, loop_id),
        ).fetchall()
    assert [row["status"] for row in rows] == ["SUPERSEDED", "SUPERSEDED"]


def test_fault_09_unauthorized_capability_fails_adapter_boundary(
    tmp_path: Path,
) -> None:
    _, service, registry, loop_id, _, proposal, staged = _prepare_registration(tmp_path)
    result = _register(service, loop_id, proposal, staged)
    records = InsuranceProtocolRecordSetV1.model_validate_json(
        canonical_json_bytes(result["protocol_state"]["record_set"])
    )
    forged = records.intent.model_copy(update={"capability_id": "source.delete@1"})
    with pytest.raises((LocalArtifactRegistryError, ValueError)):
        registry.execute(
            intent=forged,
            staged=records.staged_artifact,
            executed_at=records.action_receipt.committed_at,
        )
    assert registry.effect_count() == 1


def test_fault_10_adapter_unavailable_before_effect_is_safe_block(
    tmp_path: Path,
) -> None:
    fault = FaultOnce("AFTER_STATUS_BEFORE_OUTCOME_CAS")
    _, service, registry, loop_id, _, proposal, staged = _prepare_registration(
        tmp_path, registry_fault=fault
    )
    with pytest.raises(ClaimLoopServiceError, match="before a durable effect"):
        _register(service, loop_id, proposal, staged)
    assert fault.fired
    assert registry.effect_count() == 0
    assert (
        service.protocol_state(session_id=SESSION, loop_id=loop_id)["protocol_status"]
        == "execution_started"
    )


def test_fault_11_timeout_before_commit_cancels_on_same_intent(
    tmp_path: Path,
) -> None:
    clock_holder = {}
    fault = FaultOnce(
        "AFTER_EXECUTION_START",
        action=lambda: clock_holder["clock"].advance(301),
    )
    _, service, registry, loop_id, clock, proposal, staged = _prepare_registration(
        tmp_path, service_fault=fault
    )
    clock_holder["clock"] = clock
    with pytest.raises(ClaimLoopServiceError, match="before a durable effect"):
        _register(service, loop_id, proposal, staged)
    cancelled = _register(service, loop_id, proposal, staged)
    assert cancelled["protocol_state"]["protocol_status"] == "cancelled"
    assert registry.effect_count() == 0


def test_fault_12_response_loss_replays_completed_journal_result(
    tmp_path: Path,
) -> None:
    fault = FaultOnce("AFTER_REPLAN")
    _, service, registry, loop_id, _, proposal, staged = _prepare_registration(
        tmp_path, service_fault=fault
    )
    with pytest.raises(RuntimeError, match="AFTER_REPLAN"):
        _register(service, loop_id, proposal, staged)
    recovered = _register(service, loop_id, proposal, staged)
    assert recovered["protocol_state"]["protocol_status"] == "replanned"
    assert registry.effect_count() == 1


def test_crash_after_observation_completes_exactly_one_v2_receipt(
    tmp_path: Path,
) -> None:
    fault = FaultOnce("AFTER_REPLAN_COMMIT_BEFORE_RECEIPT")
    storage, service, registry, loop_id, clock, proposal, staged = (
        _prepare_registration(tmp_path, service_fault=fault)
    )
    with pytest.raises(RuntimeError, match="AFTER_REPLAN_COMMIT_BEFORE_RECEIPT"):
        _register(service, loop_id, proposal, staged)
    interrupted_events = service.store.events(session_id=SESSION, loop_id=loop_id)
    assert interrupted_events[-1].event_type == "OBSERVATION_INGESTED"
    assert not any(
        event.event_type == "PROTOCOL_REPLAN_RECEIPT_RECORDED"
        for event in interrupted_events
    )
    interrupted = service.protocol_state(session_id=SESSION, loop_id=loop_id)
    assert interrupted["protocol_status"] == "replan_receipt_pending"
    assert interrupted["thin_waist_record_set"]["action_receipt"] is None

    restarted = ClaimLoopService(
        storage,
        artifact_interpreter=DeterministicMouldArtifactInterpreter(),
        cycle_pipeline=_cycle_pipeline(storage),
        cycle_transport_mode="deterministic_test_double",
        source_pipeline=_cycle_pipeline(storage),
        protocol_adapter=registry,
        correction_adapters={
            MouldNeutralAssessmentCorrectionAdapterV1.adapter_id: (
                MouldNeutralAssessmentCorrectionAdapterV1()
            )
        },
        clock=clock,
    )
    recovered = _register(restarted, loop_id, proposal, staged)
    replayed = _register(restarted, loop_id, proposal, staged)
    assert canonical_json_bytes(replayed) == canonical_json_bytes(recovered)
    recovered_events = restarted.store.events(session_id=SESSION, loop_id=loop_id)
    assert (
        sum(
            event.event_type == "PROTOCOL_REPLAN_RECEIPT_RECORDED"
            for event in recovered_events
        )
        == 1
    )
    assert recovered["protocol_state"]["protocol_status"] == "replanned"
    assert (
        recovered["protocol_state"]["thin_waist_record_set"]["action_receipt"]
        is not None
    )
    assert registry.effect_count() == 1
    assert storage.model_calls() == []


def test_fault_13_crash_after_intent_before_execution_resumes_once(
    tmp_path: Path,
) -> None:
    fault = FaultOnce("AFTER_INTENT_JOURNAL")
    _, service, registry, loop_id, _, proposal, staged = _prepare_registration(
        tmp_path, service_fault=fault
    )
    with pytest.raises(RuntimeError, match="AFTER_INTENT_JOURNAL"):
        _register(service, loop_id, proposal, staged)
    assert registry.effect_count() == 0
    recovered = _register(service, loop_id, proposal, staged)
    assert recovered["protocol_state"]["protocol_status"] == "replanned"
    assert registry.effect_count() == 1


def test_startup_reconciler_preserves_expired_protocol_partial_lineage(
    tmp_path: Path,
) -> None:
    fault = FaultOnce("AFTER_INTENT_JOURNAL")
    _, service, registry, loop_id, clock, proposal, staged = _prepare_registration(
        tmp_path, service_fault=fault
    )
    with pytest.raises(RuntimeError, match="AFTER_INTENT_JOURNAL"):
        _register(service, loop_id, proposal, staged)
    clock.advance(service.CLIENT_REQUEST_TTL_SECONDS + 1)
    reconciliation = service.reconcile_abandoned_requests(now=clock())
    assert reconciliation["active_partial_lineage"] == 1
    binding = service.store.client_request(
        session_id=SESSION,
        loop_id=loop_id,
        idempotency_key="register-neutral-assessment-0001",
        request_type="insurance_register",
        request_sha256=service._protocol_entries(
            service.store.events(session_id=SESSION, loop_id=loop_id)
        )[0][0].command["client_request_sha256"],
    )
    assert binding["status"] == "RESERVED"
    recovered = _register(service, loop_id, proposal, staged)
    assert recovered["protocol_state"]["protocol_status"] == "cancelled"
    assert registry.effect_count() == 0


def test_startup_reconciler_completes_v2_terminal_lineage_without_retry(
    tmp_path: Path,
) -> None:
    fault = FaultOnce("AFTER_REPLAN")
    _, service, registry, loop_id, clock, proposal, staged = _prepare_registration(
        tmp_path, service_fault=fault
    )
    with pytest.raises(RuntimeError, match="AFTER_REPLAN"):
        _register(service, loop_id, proposal, staged)
    clock.advance(service.CLIENT_REQUEST_TTL_SECONDS + 1)
    reconciliation = service.reconcile_abandoned_requests(now=clock())
    assert reconciliation["completed_lineage"] == 1
    recovered = _register(service, loop_id, proposal, staged)
    assert recovered["protocol_state"]["protocol_status"] == "replanned"
    assert registry.effect_count() == 1


def test_fault_14_commit_claim_unknown_reconciles_without_execute_retry(
    tmp_path: Path,
) -> None:
    fault = FaultOnce("AFTER_COMMIT_CLAIM_BEFORE_ARTIFACT")
    _, service, registry, loop_id, _, proposal, staged = _prepare_registration(
        tmp_path, registry_fault=fault
    )
    unknown = _register(service, loop_id, proposal, staged)
    assert unknown["protocol_state"]["protocol_status"] == "dispatch_unknown"
    unknown_events = service.store.events(session_id=SESSION, loop_id=loop_id)
    unknown_event = next(
        event for event in unknown_events if event.event_type == "DISPATCH_UNKNOWN"
    )
    origin_records = service._protocol_entries(unknown_events)[0][1]
    request_sha256 = unknown_event.command["origin_client_request_sha256"]
    intent = unknown["protocol_state"]["record_set"]["intent"]["intent_sha256"]
    recovered = service.reconcile_protocol_intent(
        session_id=SESSION,
        loop_id=loop_id,
        intent_sha256=intent,
        idempotency_key="register-neutral-assessment-0001",
    )
    assert recovered["protocol_state"]["protocol_status"] == "replanned"
    assert registry.effect_count() == 1

    # A stale caller can replay its historical UNKNOWN transition only after
    # another caller has completed the same request.  The store must return
    # the canonical terminal prefix without the historical receipt, and the
    # service must resolve to the immutable completed response rather than
    # synthesize a mixed revision/state envelope.
    canonical, stale_receipt, _ = service.store.append_or_return_protocol_winner(
        session_id=SESSION,
        loop_id=loop_id,
        event_type="DISPATCH_UNKNOWN",
        event_kind="dispatch-unknown",
        client_idempotency_key="register-neutral-assessment-0001",
        request_sha256=request_sha256,
        command=unknown_event.command,
        timestamp=unknown_event.created_at,
        expected_revision=unknown_event.sequence - 1,
    )
    assert stale_receipt is None
    stale_response = service._resume_protocol_registration(
        state=canonical,
        records=origin_records,
        client_idempotency_key="register-neutral-assessment-0001",
        request_sha256=request_sha256,
        allow_execute=False,
    )
    assert canonical_json_bytes(stale_response) == canonical_json_bytes(recovered)
    receipt = stale_response["command_receipt"]
    assert receipt["revision"] == stale_response["revision"]
    assert receipt["state_sha256"] == stale_response["state_sha256"]
    assert receipt["event_sha256"] == canonical.last_event_sha256


def test_unknown_response_cannot_mix_with_concurrent_terminal_projection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fault = FaultOnce("AFTER_COMMIT_CLAIM_BEFORE_ARTIFACT")
    _, service, registry, loop_id, _, proposal, staged = _prepare_registration(
        tmp_path,
        registry_fault=fault,
    )
    unknown = _register(service, loop_id, proposal, staged)
    assert unknown["protocol_state"]["protocol_status"] == "dispatch_unknown"
    events = service.store.events(session_id=SESSION, loop_id=loop_id)
    origin_records = service._protocol_entries(events)[0][1]
    request_sha256 = service._protocol_entries(events)[0][0].command[
        "client_request_sha256"
    ]
    intent_sha256 = origin_records.intent.intent_sha256
    original_response = service._response
    reconciled: list[dict[str, object]] = []
    raced = False

    def racing_response(state, receipt):
        nonlocal raced
        response = original_response(state, receipt)
        if not raced:
            raced = True
            reconciled.append(
                service.reconcile_protocol_intent(
                    session_id=SESSION,
                    loop_id=loop_id,
                    intent_sha256=intent_sha256,
                    idempotency_key="register-neutral-assessment-0001",
                )
            )
        return response

    monkeypatch.setattr(service, "_response", racing_response)
    stale = service._resume_protocol_registration(
        state=service.state(session_id=SESSION, loop_id=loop_id),
        records=origin_records,
        client_idempotency_key="register-neutral-assessment-0001",
        request_sha256=request_sha256,
        allow_execute=False,
    )
    assert raced is True
    assert len(reconciled) == 1
    assert canonical_json_bytes(stale) == canonical_json_bytes(reconciled[0])
    assert stale["protocol_state"]["protocol_status"] == "replanned"
    assert stale["revision"] == stale["protocol_state"]["base_revision"]
    assert stale["state_sha256"] == stale["protocol_state"]["base_state_sha256"]
    assert stale["command_receipt"]["revision"] == stale["revision"]
    assert stale["command_receipt"]["state_sha256"] == stale["state_sha256"]
    assert registry.effect_count() == 1


def test_terminal_response_uses_one_prefix_during_concurrent_correction(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, service, registry, loop_id, _, proposal, staged = _prepare_registration(
        tmp_path
    )
    original_projection = service._protocol_projection
    raced = False

    def racing_projection(*, state, events):
        nonlocal raced
        if not raced and any(
            event.event_type == "PROTOCOL_REPLAN_RECEIPT_RECORDED"
            for event in events
        ):
            raced = True
            prepared = service.prepare_protocol_correction(
                session_id=SESSION,
                loop_id=loop_id,
                idempotency_key="prepare-terminal-race-correction-0001",
                correction_adapter_id=(
                    MouldNeutralAssessmentCorrectionAdapterV1.adapter_id
                ),
            )
            service.apply_correction(
                session_id=SESSION,
                loop_id=loop_id,
                correction_id=prepared["correction_id"],
                idempotency_key="apply-terminal-race-correction-0001",
            )
        return original_projection(state=state, events=events)

    monkeypatch.setattr(service, "_protocol_projection", racing_projection)
    terminal = _register(service, loop_id, proposal, staged)
    replay = _register(service, loop_id, proposal, staged)
    current = service.protocol_state(session_id=SESSION, loop_id=loop_id)
    assert raced is True
    assert canonical_json_bytes(replay) == canonical_json_bytes(terminal)
    assert terminal["revision"] == terminal["protocol_state"]["base_revision"]
    assert (
        terminal["state_sha256"]
        == terminal["protocol_state"]["base_state_sha256"]
    )
    assert (
        terminal["command_receipt"]["event_sha256"]
        == terminal["protocol_state"]["last_event_sha256"]
    )
    assert current["base_revision"] == terminal["revision"] + 1
    assert current["correction_count"] == 1
    assert registry.effect_count() == 1


@pytest.mark.parametrize(
    ("fatal_phase", "expected_unknown_count"),
    (
        ("AFTER_COMMIT_CLAIM_BEFORE_ARTIFACT", 1),
        ("AFTER_ARTIFACT_BEFORE_EFFECT_RECEIPT", 0),
    ),
)
def test_process_death_after_commit_resumes_from_registry_authority(
    tmp_path: Path,
    fatal_phase: str,
    expected_unknown_count: int,
) -> None:
    fault = FaultOnce(fatal_phase, action=_kill_process)
    storage, service, registry, loop_id, clock, proposal, staged = (
        _prepare_registration(tmp_path, registry_fault=fault)
    )
    with pytest.raises(SimulatedProcessDeath):
        _register(service, loop_id, proposal, staged)
    before = service.store.events(session_id=SESSION, loop_id=loop_id)
    assert before[-1].event_type == "PROTOCOL_EXECUTION_STARTED"
    assert registry.effect_count() == 1

    restarted_registry = LocalArtifactRegistryAdapterV1(registry.root)
    restarted = _recreate_service(
        storage=storage,
        registry=restarted_registry,
        clock=clock,
    )
    intent_sha256 = restarted.protocol_state(session_id=SESSION, loop_id=loop_id)[
        "record_set"
    ]["intent"]["intent_sha256"]
    result = restarted.reconcile_protocol_intent(
        session_id=SESSION,
        loop_id=loop_id,
        intent_sha256=intent_sha256,
        idempotency_key="register-neutral-assessment-0001",
    )
    assert result["protocol_state"]["protocol_status"] == "replanned"
    events = restarted.store.events(session_id=SESSION, loop_id=loop_id)
    assert sum(event.event_type == "DISPATCH_UNKNOWN" for event in events) == (
        expected_unknown_count
    )
    assert (
        sum(event.event_type == "PROTOCOL_ACTION_RECEIPT_RECORDED" for event in events)
        == 1
    )
    assert restarted_registry.effect_count() == 1
    replay = _register(restarted, loop_id, proposal, staged)
    assert canonical_json_bytes(replay) == canonical_json_bytes(result)


def test_fault_15_crash_after_receipt_resumes_epistemic_chain(
    tmp_path: Path,
) -> None:
    fault = FaultOnce("AFTER_ACTION_RECEIPT")
    _, service, registry, loop_id, _, proposal, staged = _prepare_registration(
        tmp_path, service_fault=fault
    )
    with pytest.raises(RuntimeError, match="AFTER_ACTION_RECEIPT"):
        _register(service, loop_id, proposal, staged)
    recovered = _register(service, loop_id, proposal, staged)
    assert recovered["protocol_state"]["protocol_status"] == "replanned"
    assert registry.effect_count() == 1


def test_fault_16_corrupt_checkpoint_rebuilds_exact_protocol_projection(
    tmp_path: Path,
) -> None:
    _, service, _, loop_id, _, proposal, staged = _prepare_registration(tmp_path)
    result = _register(service, loop_id, proposal, staged)
    expected = result["protocol_state"]
    with service.store.connect() as connection:
        connection.execute(
            "UPDATE claim_loop_checkpoints SET state_json='{' WHERE session_id=? AND loop_id=?",
            (SESSION, loop_id),
        )
    recovered = service.protocol_state(session_id=SESSION, loop_id=loop_id)
    assert canonical_json_bytes(recovered) == canonical_json_bytes(expected)


def test_fault_17_cancel_before_execute_claims_zero_effects(tmp_path: Path) -> None:
    fault = FaultOnce("AFTER_INTENT_JOURNAL")
    _, service, registry, loop_id, _, proposal, staged = _prepare_registration(
        tmp_path, service_fault=fault
    )
    with pytest.raises(RuntimeError, match="AFTER_INTENT_JOURNAL"):
        _register(service, loop_id, proposal, staged)
    protocol = service.protocol_state(session_id=SESSION, loop_id=loop_id)
    intent = protocol["record_set"]["intent"]["intent_sha256"]
    cancelled = service.cancel_protocol_intent(
        session_id=SESSION,
        loop_id=loop_id,
        intent_sha256=intent,
        idempotency_key="register-neutral-assessment-0001",
    )
    assert cancelled["protocol_state"]["protocol_status"] == "cancelled"
    assert registry.effect_count() == 0


def test_fault_18_cancel_after_commit_preserves_committed_result(
    tmp_path: Path,
) -> None:
    _, service, registry, loop_id, _, proposal, staged = _prepare_registration(tmp_path)
    committed = _register(service, loop_id, proposal, staged)
    intent = committed["protocol_state"]["record_set"]["intent"]["intent_sha256"]
    preserved = service.cancel_protocol_intent(
        session_id=SESSION,
        loop_id=loop_id,
        intent_sha256=intent,
        idempotency_key="register-neutral-assessment-0001",
    )
    assert canonical_json_bytes(preserved) == canonical_json_bytes(committed)
    assert registry.effect_count() == 1


def test_fault_19_case_local_correction_replans_and_reloads(
    tmp_path: Path,
) -> None:
    storage, service, registry, loop_id, clock, proposal, staged = (
        _prepare_registration(tmp_path)
    )
    committed = _register(service, loop_id, proposal, staged)
    before = service.state(session_id=SESSION, loop_id=loop_id)
    before_unrelated = tuple(
        value for value in before.facts if value.get("fact_id") != "fact_cause"
    )
    prepared = service.prepare_protocol_correction(
        session_id=SESSION,
        loop_id=loop_id,
        idempotency_key="prepare-neutral-correction-0001",
        correction_adapter_id=(MouldNeutralAssessmentCorrectionAdapterV1.adapter_id),
    )
    replayed = service.prepare_protocol_correction(
        session_id=SESSION,
        loop_id=loop_id,
        idempotency_key="prepare-neutral-correction-0001",
        correction_adapter_id=(MouldNeutralAssessmentCorrectionAdapterV1.adapter_id),
    )
    assert canonical_json_bytes(replayed) == canonical_json_bytes(prepared)
    preview = prepared["preview"]
    assert preview["parent_state_sha256"] == before.state_sha256
    assert (
        preview["unrelated_facts_before_sha256"]
        == preview["unrelated_facts_after_sha256"]
    )
    assert preview["before_fact_sha256"] != preview["expected_after_fact_sha256"]
    assert (
        preview["before_evidence_sha256"]
        != preview["expected_after_evidence_sha256"]
    )
    applied = service.apply_correction(
        session_id=SESSION,
        loop_id=loop_id,
        correction_id=prepared["correction_id"],
        idempotency_key="apply-neutral-correction-0001",
    )
    assert applied["revision"] > committed["revision"]
    corrected = service.state(session_id=SESSION, loop_id=loop_id)
    fact = next(
        value for value in corrected.facts if value.get("fact_id") == "fact_cause"
    )
    evidence = next(
        value
        for value in corrected.checklist["items"]
        if value.get("item_id") == "technical_assessment"
    )
    assert fact["state"] == "unknown"
    assert evidence["status"] == "provided_insufficient"
    assert (
        tuple(
            value for value in corrected.facts if value.get("fact_id") != "fact_cause"
        )
        == before_unrelated
    )
    assert corrected.six_agent_cycle_receipt.cycle_kind == "correction"
    assert len(corrected.six_agent_cycle_receipt.agent_ids) == 6
    assert len(corrected.six_agent_cycle_receipt.deterministic_gate_ids) == 3
    correction_projection = service.protocol_state(
        session_id=SESSION, loop_id=loop_id
    )
    delta = correction_projection["latest_correction"]
    assert correction_projection["correction_count"] == 1
    assert delta["correction_id"] == prepared["correction_id"]
    assert delta["before_fact_sha256"] != delta["after_fact_sha256"]
    assert delta["after_fact_sha256"] == preview["expected_after_fact_sha256"]
    assert (
        delta["after_evidence_sha256"]
        == preview["expected_after_evidence_sha256"]
    )
    assert (
        delta["unrelated_facts_before_sha256"]
        == delta["unrelated_facts_after_sha256"]
    )

    reloaded_service = ClaimLoopService(
        storage,
        artifact_interpreter=DeterministicMouldArtifactInterpreter(),
        cycle_pipeline=_cycle_pipeline(storage),
        cycle_transport_mode="deterministic_test_double",
        source_pipeline=_cycle_pipeline(storage),
        protocol_adapter=registry,
        correction_adapters={
            MouldNeutralAssessmentCorrectionAdapterV1.adapter_id: (
                MouldNeutralAssessmentCorrectionAdapterV1()
            )
        },
        clock=clock,
    )
    reloaded = reloaded_service.state(session_id=SESSION, loop_id=loop_id)
    assert reloaded.state_sha256 == corrected.state_sha256
    assert reloaded.model_dump(mode="json") == corrected.model_dump(mode="json")
    assert canonical_json_bytes(
        reloaded_service.protocol_state(session_id=SESSION, loop_id=loop_id)
    ) == canonical_json_bytes(correction_projection)


def test_handler_selects_hash_bound_correction_and_can_restore_exact_source(
    tmp_path: Path,
) -> None:
    _, service, _, loop_id, _, proposal, staged = _prepare_registration(tmp_path)
    _register(service, loop_id, proposal, staged)
    before = service.state(session_id=SESSION, loop_id=loop_id)

    options = service.protocol_correction_options(
        session_id=SESSION, loop_id=loop_id
    )
    assert options["revision"] == before.revision
    assert options["state_sha256"] == before.state_sha256
    assert len(options["candidates"]) == 1
    candidate = options["candidates"][0]
    assert candidate["target_fact_id"] == "fact_cause"
    assert candidate["target_evidence_item_id"] == "technical_assessment"
    assert candidate["semantic_delta_id"] == "withdraw_decision_sufficiency_v1"

    event_count = len(
        service.store.snapshot(session_id=SESSION, loop_id=loop_id)[1]
    )
    with pytest.raises(ClaimLoopServiceError, match="selection differs"):
        service.prepare_protocol_correction(
            session_id=SESSION,
            loop_id=loop_id,
            idempotency_key="prepare-selected-correction-tampered",
            candidate_sha256="0" * 64,
            target_assertion_sha256=candidate["target_assertion_sha256"],
            target_interpretation_sha256=candidate["target_interpretation_sha256"],
            semantic_delta_id=candidate["semantic_delta_id"],
            expected_revision=candidate["revision"],
        )
    assert (
        len(service.store.snapshot(session_id=SESSION, loop_id=loop_id)[1])
        == event_count
    )

    prepared = service.prepare_protocol_correction(
        session_id=SESSION,
        loop_id=loop_id,
        idempotency_key="prepare-selected-correction-0001",
        candidate_sha256=candidate["candidate_sha256"],
        target_assertion_sha256=candidate["target_assertion_sha256"],
        target_interpretation_sha256=candidate["target_interpretation_sha256"],
        semantic_delta_id=candidate["semantic_delta_id"],
        expected_revision=candidate["revision"],
    )
    assert prepared["selection"] == candidate
    service.apply_correction(
        session_id=SESSION,
        loop_id=loop_id,
        correction_id=prepared["correction_id"],
        idempotency_key="apply-selected-correction-0001",
    )

    with pytest.raises(ClaimLoopServiceError) as stale_first:
        service.apply_correction(
            session_id=SESSION,
            loop_id=loop_id,
            correction_id=prepared["correction_id"],
            idempotency_key="apply-stale-selected-correction-0001",
        )
    assert stale_first.value.conflict_envelope is not None
    assert (
        stale_first.value.conflict_envelope["error_code"]
        == "REQUEST_PREFIX_SUPERSEDED"
    )
    with pytest.raises(ClaimLoopServiceError) as stale_replay:
        service.apply_correction(
            session_id=SESSION,
            loop_id=loop_id,
            correction_id=prepared["correction_id"],
            idempotency_key="apply-stale-selected-correction-0001",
        )
    assert stale_replay.value.conflict_envelope == stale_first.value.conflict_envelope

    rollback_options = service.protocol_correction_options(
        session_id=SESSION, loop_id=loop_id
    )
    assert len(rollback_options["candidates"]) == 1
    rollback = rollback_options["candidates"][0]
    assert rollback["operation"] == "rollback_scoped_correction"
    assert rollback["semantic_delta_id"] == "restore_admitted_assertion_v1"
    rollback_prepared = service.prepare_protocol_correction(
        session_id=SESSION,
        loop_id=loop_id,
        idempotency_key="prepare-selected-rollback-0001",
        candidate_sha256=rollback["candidate_sha256"],
        target_assertion_sha256=rollback["target_assertion_sha256"],
        target_interpretation_sha256=rollback["target_interpretation_sha256"],
        semantic_delta_id=rollback["semantic_delta_id"],
        expected_revision=rollback["revision"],
    )
    service.apply_correction(
        session_id=SESSION,
        loop_id=loop_id,
        correction_id=rollback_prepared["correction_id"],
        idempotency_key="apply-selected-rollback-0001",
    )
    restored = service.state(session_id=SESSION, loop_id=loop_id)
    restored_fact = next(
        value for value in restored.facts if value.get("fact_id") == "fact_cause"
    )
    restored_evidence = next(
        value
        for value in restored.checklist["items"]
        if value.get("item_id") == "technical_assessment"
    )
    original_fact = next(
        value for value in before.facts if value.get("fact_id") == "fact_cause"
    )
    original_evidence = next(
        value
        for value in before.checklist["items"]
        if value.get("item_id") == "technical_assessment"
    )
    assert restored_fact == original_fact
    assert restored_evidence == original_evidence
    assert service.protocol_correction_options(
        session_id=SESSION, loop_id=loop_id
    )["candidates"] == []


def test_fault_20_tampered_action_receipt_locator_fails_without_journal_drift(
    tmp_path: Path,
) -> None:
    _, service, registry, loop_id, _, proposal, staged = _prepare_registration(tmp_path)
    result = _register(service, loop_id, proposal, staged)
    before = service.state(session_id=SESSION, loop_id=loop_id)
    records = InsuranceProtocolRecordSetV1.model_validate_json(
        canonical_json_bytes(result["protocol_state"]["record_set"])
    )
    assert records.action_receipt is not None
    ack_path = (
        registry.ack_root
        / records.intent.effect_idempotency_key
        / f"{records.intent.intent_sha256}.json"
    )
    tampered = json.loads(ack_path.read_text(encoding="utf-8"))
    tampered["artifact_uri"] = "casepath-artifact://sha256/" + "f" * 64
    tampered["receipt_sha256"] = digest_value(
        {key: value for key, value in tampered.items() if key != "receipt_sha256"}
    )
    ack_path.write_bytes(canonical_json_bytes(tampered))
    with pytest.raises(LocalArtifactRegistryError, match="ACKNOWLEDGEMENT_INVALID"):
        registry.status(intent=records.intent)
    with pytest.raises(ClaimLoopServiceError, match="ACKNOWLEDGEMENT_INVALID"):
        service.protocol_state(session_id=SESSION, loop_id=loop_id)
    with pytest.raises(ClaimLoopServiceError, match="ACKNOWLEDGEMENT_INVALID"):
        _register(service, loop_id, proposal, staged)
    after = service.state(session_id=SESSION, loop_id=loop_id)
    assert after.state_sha256 == before.state_sha256
    assert registry.effect_count() == 1


def test_concurrent_same_key_registration_never_cancels_winner(
    tmp_path: Path,
) -> None:
    entered = threading.Event()
    release = threading.Event()

    def block_before_commit(phase: str) -> None:
        if phase == "AFTER_STATUS_BEFORE_OUTCOME_CAS":
            entered.set()
            assert release.wait(timeout=10)

    _, service, registry, loop_id, _, proposal, staged = _prepare_registration(
        tmp_path, registry_fault=block_before_commit
    )
    results: list[dict[str, object]] = []
    errors: list[BaseException] = []

    def invoke() -> None:
        try:
            results.append(_register(service, loop_id, proposal, staged))
        except BaseException as exc:  # pragma: no cover - asserted below
            errors.append(exc)

    winner = threading.Thread(target=invoke)
    duplicate = threading.Thread(target=invoke)
    winner.start()
    assert entered.wait(timeout=10)
    duplicate.start()
    time.sleep(0.05)
    release.set()
    winner.join(timeout=15)
    duplicate.join(timeout=15)
    assert not winner.is_alive() and not duplicate.is_alive()
    assert errors == []
    assert len(results) == 2
    assert canonical_json_bytes(results[0]) == canonical_json_bytes(results[1])
    assert results[0]["protocol_state"]["protocol_status"] == "replanned"
    assert registry.effect_count() == 1


def test_concurrent_callers_before_execution_marker_share_one_lineage(
    tmp_path: Path,
) -> None:
    barrier = threading.Barrier(2)

    def block_before_marker(phase: str) -> None:
        if phase == "BEFORE_EXECUTION_START":
            barrier.wait(timeout=10)

    _, service, registry, loop_id, _, proposal, staged = _prepare_registration(
        tmp_path, service_fault=block_before_marker
    )
    results: list[dict[str, object]] = []
    errors: list[BaseException] = []

    def invoke() -> None:
        try:
            results.append(_register(service, loop_id, proposal, staged))
        except BaseException as exc:  # pragma: no cover - asserted below
            errors.append(exc)

    callers = [threading.Thread(target=invoke) for _ in range(2)]
    for caller in callers:
        caller.start()
    for caller in callers:
        caller.join(timeout=20)
    assert all(not caller.is_alive() for caller in callers)
    assert errors == []
    assert len(results) == 2
    assert canonical_json_bytes(results[0]) == canonical_json_bytes(results[1])
    events = service.store.events(session_id=SESSION, loop_id=loop_id)
    assert (
        sum(event.event_type == "PROTOCOL_EXECUTION_STARTED" for event in events) == 1
    )
    assert registry.effect_count() == 1


def test_live_registration_and_reconcile_never_cancel_shared_effect(
    tmp_path: Path,
) -> None:
    entered = threading.Event()
    release = threading.Event()

    def block_before_commit(phase: str) -> None:
        if phase == "AFTER_STATUS_BEFORE_OUTCOME_CAS":
            entered.set()
            assert release.wait(timeout=10)

    _, service, registry, loop_id, _, proposal, staged = _prepare_registration(
        tmp_path, registry_fault=block_before_commit
    )
    results: list[dict[str, object]] = []
    errors: list[BaseException] = []

    def register() -> None:
        try:
            results.append(_register(service, loop_id, proposal, staged))
        except BaseException as exc:  # pragma: no cover - asserted below
            errors.append(exc)

    winner = threading.Thread(target=register)
    winner.start()
    assert entered.wait(timeout=10)
    protocol = service.protocol_state(session_id=SESSION, loop_id=loop_id)
    intent_sha256 = protocol["record_set"]["intent"]["intent_sha256"]

    def reconcile() -> None:
        try:
            results.append(
                service.reconcile_protocol_intent(
                    session_id=SESSION,
                    loop_id=loop_id,
                    intent_sha256=intent_sha256,
                    idempotency_key="register-neutral-assessment-0001",
                )
            )
        except BaseException as exc:  # pragma: no cover - asserted below
            errors.append(exc)

    reconciler = threading.Thread(target=reconcile)
    reconciler.start()
    time.sleep(0.05)
    release.set()
    winner.join(timeout=20)
    reconciler.join(timeout=20)
    assert not winner.is_alive() and not reconciler.is_alive()
    assert errors == []
    assert len(results) == 2
    assert canonical_json_bytes(results[0]) == canonical_json_bytes(results[1])
    assert registry.effect_count() == 1


@pytest.mark.parametrize(
    "competitor_kind",
    ("duplicate", "explicit_reconciler", "startup_reconciler"),
)
@pytest.mark.parametrize(
    ("adapter_state", "fault_phase", "expected_status", "unknown_count"),
    (
        ("NONE", "AFTER_STATUS_BEFORE_OUTCOME_CAS", None, 0),
        (
            "COMMIT_CLAIMED",
            "AFTER_COMMIT_CLAIM_BEFORE_ARTIFACT",
            "unknown",
            1,
        ),
        (
            "COMMITTED",
            "AFTER_ARTIFACT_BEFORE_EFFECT_RECEIPT",
            "committed",
            0,
        ),
    ),
)
def test_protocol_transition_election_barrier_matrix(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    competitor_kind: str,
    adapter_state: str,
    fault_phase: str,
    expected_status: str | None,
    unknown_count: int,
) -> None:
    owner_at_boundary = threading.Event()
    release_owner = threading.Event()
    competitor_observed_status = threading.Event()
    counter_lock = threading.Lock()
    calls = {"execute": 0, "cancel": 0}

    original_execute = LocalArtifactRegistryAdapterV1.execute
    original_cancel = LocalArtifactRegistryAdapterV1.cancel
    original_status = LocalArtifactRegistryAdapterV1.status

    def counted_execute(self, *args, **kwargs):
        with counter_lock:
            calls["execute"] += 1
        return original_execute(self, *args, **kwargs)

    def counted_cancel(self, *args, **kwargs):
        with counter_lock:
            calls["cancel"] += 1
        return original_cancel(self, *args, **kwargs)

    def observed_status(self, *args, **kwargs):
        receipt = original_status(self, *args, **kwargs)
        observed = None if receipt is None else receipt.status.value
        if (
            threading.current_thread().name == "protocol-competitor"
            and observed == expected_status
        ):
            competitor_observed_status.set()
        return receipt

    monkeypatch.setattr(LocalArtifactRegistryAdapterV1, "execute", counted_execute)
    monkeypatch.setattr(LocalArtifactRegistryAdapterV1, "cancel", counted_cancel)
    monkeypatch.setattr(LocalArtifactRegistryAdapterV1, "status", observed_status)

    def stop_owner_at_durable_state(phase: str) -> None:
        if phase == fault_phase and threading.current_thread().name == "protocol-owner":
            owner_at_boundary.set()
            assert release_owner.wait(timeout=30)

    storage, service, registry, loop_id, clock, proposal, staged = (
        _prepare_registration(tmp_path, registry_fault=stop_owner_at_durable_state)
    )
    owner_results: list[dict[str, object]] = []
    competitor_results: list[dict[str, object]] = []
    errors: list[BaseException] = []

    def owner() -> None:
        try:
            owner_results.append(_register(service, loop_id, proposal, staged))
        except BaseException as exc:  # pragma: no cover - asserted below
            errors.append(exc)

    owner_thread = threading.Thread(target=owner, name="protocol-owner")
    owner_thread.start()
    assert owner_at_boundary.wait(timeout=30), adapter_state
    protocol = service.protocol_state(session_id=SESSION, loop_id=loop_id)
    intent_sha256 = protocol["record_set"]["intent"]["intent_sha256"]

    fresh_registry = LocalArtifactRegistryAdapterV1(registry.root)
    fresh_service = _recreate_service(
        storage=storage,
        registry=fresh_registry,
        clock=clock,
    )

    def competitor() -> None:
        try:
            if competitor_kind == "duplicate":
                competitor_results.append(_register(service, loop_id, proposal, staged))
            elif competitor_kind == "explicit_reconciler":
                competitor_results.append(
                    service.reconcile_protocol_intent(
                        session_id=SESSION,
                        loop_id=loop_id,
                        intent_sha256=intent_sha256,
                        idempotency_key="register-neutral-assessment-0001",
                    )
                )
            else:
                competitor_results.append(
                    fresh_service.reconcile_abandoned_requests(
                        now=clock(),
                        recover_protocol_effects=True,
                    )
                )
        except BaseException as exc:  # pragma: no cover - asserted below
            errors.append(exc)

    competitor_thread = threading.Thread(
        target=competitor,
        name="protocol-competitor",
    )
    competitor_thread.start()
    assert competitor_observed_status.wait(timeout=30), (
        competitor_kind,
        adapter_state,
    )
    if adapter_state != "NONE":
        competitor_thread.join(timeout=90)
        assert not competitor_thread.is_alive()
    release_owner.set()
    owner_thread.join(timeout=90)
    competitor_thread.join(timeout=90)
    assert not owner_thread.is_alive() and not competitor_thread.is_alive()
    assert errors == []
    assert len(owner_results) == 1
    assert len(competitor_results) == 1
    assert calls == {"execute": 1, "cancel": 0}
    assert registry.effect_count() == 1
    assert registry.content_blob_count() == 1

    terminal_service = _recreate_service(
        storage=storage,
        registry=LocalArtifactRegistryAdapterV1(registry.root),
        clock=clock,
    )
    terminal = _register(terminal_service, loop_id, proposal, staged)
    replay = _register(terminal_service, loop_id, proposal, staged)
    assert canonical_json_bytes(replay) == canonical_json_bytes(terminal)
    assert terminal["protocol_state"]["protocol_status"] == "replanned"
    events = terminal_service.store.events(session_id=SESSION, loop_id=loop_id)
    expected_once = {
        "PROTOCOL_EXECUTION_STARTED",
        "PROTOCOL_ACTION_RECEIPT_RECORDED",
        "PROTOCOL_SOURCE_OBSERVATION_RECORDED",
        "PROTOCOL_ASSERTION_NORMALIZED",
        "PROTOCOL_INTERPRETATION_RECORDED",
        "OBSERVATION_INGESTED",
        "PROTOCOL_REPLAN_RECEIPT_RECORDED",
    }
    for event_type in expected_once:
        assert sum(event.event_type == event_type for event in events) == 1
    assert sum(event.event_type == "DISPATCH_UNKNOWN" for event in events) == (
        unknown_count
    )
    origin = terminal_service._protocol_entries(events)[0][0]
    binding = terminal_service.store.client_request(
        session_id=SESSION,
        loop_id=loop_id,
        idempotency_key="register-neutral-assessment-0001",
        request_type="insurance_register",
        request_sha256=origin.command["client_request_sha256"],
    )
    assert binding["status"] == "COMPLETED"
    assert storage.model_calls() == []


def test_stale_protocol_caller_returns_canonical_newer_prefix(
    tmp_path: Path,
) -> None:
    first_fault = FaultOnce("AFTER_ACTION_RECEIPT")
    _, service, _, loop_id, _, proposal, staged = _prepare_registration(
        tmp_path,
        service_fault=first_fault,
    )
    with pytest.raises(RuntimeError, match="AFTER_ACTION_RECEIPT"):
        _register(service, loop_id, proposal, staged)
    stale_state, stale_events = service.store.snapshot(
        session_id=SESSION,
        loop_id=loop_id,
    )
    assert service._protocol_entries(stale_events)

    second_fault = FaultOnce("AFTER_NORMALIZED_ASSERTION")
    service._protocol_fault_hook = second_fault
    with pytest.raises(RuntimeError, match="AFTER_NORMALIZED_ASSERTION"):
        _register(service, loop_id, proposal, staged)
    newer_state, newer_events = service.store.snapshot(
        session_id=SESSION,
        loop_id=loop_id,
    )
    newer_entries = service._protocol_entries(newer_events)
    source_event, source_records = next(
        entry
        for entry in newer_entries
        if entry[0].event_type == "PROTOCOL_SOURCE_OBSERVATION_RECORDED"
    )
    assert source_records.source_observation is not None
    before_count = len(newer_events)
    returned_state, returned_receipt, replayed = service._append_protocol_event(
        state=stale_state,
        records=source_records,
        event_type="PROTOCOL_SOURCE_OBSERVATION_RECORDED",
        event_kind="source-observation",
        client_idempotency_key="register-neutral-assessment-0001",
        request_sha256=newer_entries[0][0].command["client_request_sha256"],
        timestamp=source_records.source_observation.observed_at,
    )
    assert replayed is False
    assert returned_receipt is None
    assert source_event.event_sha256 != newer_state.last_event_sha256
    assert returned_state.state_sha256 == newer_state.state_sha256
    assert returned_state.revision == newer_state.revision
    assert (
        len(service.store.events(session_id=SESSION, loop_id=loop_id)) == before_count
    )

    service._protocol_fault_hook = None
    terminal = _register(service, loop_id, proposal, staged)
    replay = _register(service, loop_id, proposal, staged)
    assert canonical_json_bytes(replay) == canonical_json_bytes(terminal)
    assert terminal["protocol_state"]["protocol_status"] == "replanned"


def test_journal_rebuilds_deleted_evidence_indexes_exactly(tmp_path: Path) -> None:
    _, service, _, loop_id, _, proposal, staged = _prepare_registration(tmp_path)
    _register(service, loop_id, proposal, staged)
    before = service.state(session_id=SESSION, loop_id=loop_id)
    with service.store.connect() as connection:
        connection.execute("DELETE FROM claim_loop_tool_artifacts")
        connection.execute("DELETE FROM claim_loop_acquisitions")
        connection.execute(
            "UPDATE claim_loop_checkpoints SET state_json='{' WHERE session_id=? AND loop_id=?",
            (SESSION, loop_id),
        )
    recovered = service.state(session_id=SESSION, loop_id=loop_id)
    assert recovered.model_dump(mode="json") == before.model_dump(mode="json")
    assert (
        service.store.tool_artifact(
            before.projection_ledger[-1].artifact_receipt_sha256
        )
        is not None
    )


def test_journal_repairs_corrupt_correction_and_evidence_indexes(
    tmp_path: Path,
) -> None:
    _, service, _, loop_id, _, proposal, staged = _prepare_registration(tmp_path)
    _register(service, loop_id, proposal, staged)
    prepared = service.prepare_protocol_correction(
        session_id=SESSION,
        loop_id=loop_id,
        idempotency_key="prepare-rebuild-correction-0001",
        correction_adapter_id=(MouldNeutralAssessmentCorrectionAdapterV1.adapter_id),
    )
    service.apply_correction(
        session_id=SESSION,
        loop_id=loop_id,
        correction_id=prepared["correction_id"],
        idempotency_key="apply-rebuild-correction-0001",
    )
    before = service.state(session_id=SESSION, loop_id=loop_id)
    correction = service.store.correction(prepared["correction_id"])
    assert correction is not None
    authority = service.store.correction_artifact(
        correction[0].correction_artifact_receipt_sha256
    )
    assert authority is not None
    with service.store.connect() as connection:
        connection.execute("UPDATE claim_loop_acquisitions SET acquisition_json='{}'")
        connection.execute("UPDATE claim_loop_tool_artifacts SET artifact_json='{}'")
        connection.execute("UPDATE claim_loop_corrections SET correction_json='{}'")
        connection.execute(
            "UPDATE claim_loop_correction_artifacts SET artifact_json='{}'"
        )
        connection.execute(
            "UPDATE claim_loop_checkpoints SET state_json='{' WHERE session_id=? AND loop_id=?",
            (SESSION, loop_id),
        )
    recovered = service.state(session_id=SESSION, loop_id=loop_id)
    assert recovered.model_dump(mode="json") == before.model_dump(mode="json")
    rebuilt_correction = service.store.correction(prepared["correction_id"])
    assert rebuilt_correction is not None
    assert rebuilt_correction[0] == correction[0]
    assert (
        service.store.correction_artifact(
            rebuilt_correction[0].correction_artifact_receipt_sha256
        )
        == authority
    )
    assert (
        service.store.tool_artifact(
            before.projection_ledger[-1].artifact_receipt_sha256
        )
        is not None
    )


def test_ecab_registry_adapter_contract_conformance(tmp_path: Path) -> None:
    clean_root = tmp_path / "clean"
    clean_root.mkdir()
    (
        storage,
        service,
        registry,
        loop_id,
        clock,
        proposal,
        staged,
        span,
    ) = _prepare_ecab_registration(clean_root)
    with pytest.raises(
        ClaimLoopServiceError, match="ECAB_TYPED_FACTUAL_HISTORY_STAGE_REQUIRED"
    ):
        service.stage_protocol_material(
            session_id=SESSION,
            loop_id=loop_id,
            filename="bypass.txt",
            media_type="text/plain; charset=utf-8",
            content=NEUTRAL_ASSESSMENT,
            idempotency_key="stage-bypass-must-fail-0001",
            expected_revision=proposal["revision"],
        )
    result = _register(service, loop_id, proposal, staged)
    replay = _register(service, loop_id, proposal, staged)
    assert canonical_json_bytes(replay) == canonical_json_bytes(result)
    fresh_registry = ECABFactualHistoryRegistryAdapterV1(
        clean_root / "artifact-registry"
    )
    fresh_service = _recreate_service(
        storage=storage,
        registry=fresh_registry,
        clock=clock,
    )
    assert canonical_json_bytes(
        _register(fresh_service, loop_id, proposal, staged)
    ) == canonical_json_bytes(result)
    records = InsuranceProtocolRecordSetV1.model_validate_json(
        canonical_json_bytes(result["protocol_state"]["record_set"])
    )
    assert records.decision.compatibility_action.action_kind == "register"
    assert records.intent.adapter_id == registry.adapter_id
    assert records.action_receipt is not None
    assert records.action_receipt.adapter_id == registry.adapter_id
    mapped = staged["mapped_stage_receipt"]
    assert mapped["mapped_event"]["source_event_sha256"] == span.event_sha256
    assert mapped["mapped_event"]["action_sha256"] == (
        records.decision.compatibility_action.action_sha256
    )
    assert mapped["mapped_event"]["sanitized_excerpt"] == NEUTRAL_ASSESSMENT
    assert records.staged_artifact.content_sha256 == digest_text(NEUTRAL_ASSESSMENT)
    protocol_events = [
        event
        for event in service.store.events(session_id=SESSION, loop_id=loop_id)
        if "insurance_protocol_v1" in event.command
    ]
    assert protocol_events
    assert all(
        event.command["adapter_staging_binding"]["receipt_sha256"]
        == mapped["receipt_sha256"]
        for event in protocol_events
    )
    artifact = service.store.tool_artifact(
        service.state(session_id=SESSION, loop_id=loop_id)
        .projection_ledger[-1]
        .artifact_receipt_sha256
    )
    assert artifact is not None
    assert (
        artifact.acquisition_receipt.contract
        == "casepath.source-registration-compatibility-receipt/1.0.0"
    )
    forged = records.intent.model_copy(update={"capability_id": "source.delete@1"})
    with pytest.raises((LocalArtifactRegistryError, ValueError)):
        registry.execute(
            intent=forged,
            staged=records.staged_artifact,
            executed_at=records.action_receipt.committed_at,
        )
    assert registry.effect_count() == 1
    assert storage.model_calls() == []

    unknown_root = tmp_path / "unknown"
    unknown_root.mkdir()
    fault = FaultOnce("AFTER_COMMIT_CLAIM_BEFORE_ARTIFACT")
    (
        _,
        unknown_service,
        unknown_registry,
        unknown_loop,
        _,
        unknown_proposal,
        unknown_stage,
        _,
    ) = _prepare_ecab_registration(
        unknown_root,
        registry_fault=fault,
    )
    unknown = _register(unknown_service, unknown_loop, unknown_proposal, unknown_stage)
    assert unknown["protocol_state"]["protocol_status"] == "dispatch_unknown"
    intent_sha = unknown["protocol_state"]["record_set"]["intent"]["intent_sha256"]
    reconciled = unknown_service.reconcile_protocol_intent(
        session_id=SESSION,
        loop_id=unknown_loop,
        intent_sha256=intent_sha,
        idempotency_key="register-neutral-assessment-0001",
    )
    assert reconciled["protocol_state"]["protocol_status"] == "replanned"
    assert unknown_registry.effect_count() == 1

    tamper_root = tmp_path / "tamper"
    tamper_root.mkdir()
    (
        _,
        tamper_service,
        tamper_registry,
        tamper_loop,
        _,
        tamper_proposal,
        tamper_stage,
        _,
    ) = _prepare_ecab_registration(
        tamper_root,
    )
    before = tamper_service.state(session_id=SESSION, loop_id=tamper_loop)
    receipt_path = tamper_registry.mapped_stage_root / (
        tamper_stage["staged_artifact_receipt_sha256"] + ".json"
    )
    value = json.loads(receipt_path.read_text(encoding="utf-8"))
    value["mapped_event"]["source_id"] = "source.tampered"
    receipt_path.write_bytes(canonical_json_bytes(value))
    with pytest.raises(ClaimLoopServiceError, match="MAPPED_STAGE_RECEIPT_INVALID"):
        _register(
            tamper_service,
            tamper_loop,
            tamper_proposal,
            tamper_stage,
        )
    after = tamper_service.state(session_id=SESSION, loop_id=tamper_loop)
    assert after.state_sha256 == before.state_sha256
    assert tamper_registry.effect_count() == 0

    mismatch_root = tmp_path / "mismatch"
    mismatch_root.mkdir()
    (
        _,
        mismatch_service,
        mismatch_registry,
        mismatch_loop,
        _,
    ) = _service_fixture(
        mismatch_root,
        registry_class=ECABFactualHistoryRegistryAdapterV1,
    )
    mismatch_proposal = mismatch_service.protocol_proposal(
        session_id=SESSION, loop_id=mismatch_loop
    )
    mismatch_action = EvidenceAction.model_validate(
        mismatch_proposal["registration_action"]
    )
    state = mismatch_service.state(session_id=SESSION, loop_id=mismatch_loop)
    wrong_action_span = build_ecab_factual_history_span_v1(
        event_index=0,
        previous_event_sha256=None,
        action_id="action." + "f" * 64,
        action_sha256="f" * 64,
        source_id="source.synthetic-factual-history-0002",
        source_sha256=digest_text(NEUTRAL_ASSESSMENT),
        source_version=state.record_version,
        page=1,
        sanitized_page_text=NEUTRAL_ASSESSMENT,
        text_start=0,
        text_end=len(NEUTRAL_ASSESSMENT),
        observed_at="2026-08-28T11:59:00+00:00",
    )
    assert wrong_action_span.action_sha256 != mismatch_action.action_sha256
    mismatch_errors = []
    for _ in range(2):
        with pytest.raises(ClaimLoopServiceError, match="another action") as captured:
            mismatch_service.stage_protocol_factual_history(
                session_id=SESSION,
                loop_id=mismatch_loop,
                span=wrong_action_span,
                idempotency_key="stage-factual-history-mismatch-0001",
                expected_revision=mismatch_proposal["revision"],
            )
        mismatch_errors.append(str(captured.value))
    assert mismatch_errors[0] == mismatch_errors[1]
    assert mismatch_registry.effect_count() == 0
    with mismatch_service.store.connect() as connection:
        row = connection.execute(
            """SELECT status FROM claim_loop_client_requests
            WHERE session_id=? AND loop_id=? AND idempotency_key=?""",
            (SESSION, mismatch_loop, "stage-factual-history-mismatch-0001"),
        ).fetchone()
    assert row is not None and row["status"] == "SUPERSEDED"

    stale_root = tmp_path / "stale"
    stale_root.mkdir()
    (
        _,
        stale_service,
        stale_registry,
        stale_loop,
        _,
        stale_proposal,
        stale_stage,
        stale_span,
    ) = _prepare_ecab_registration(stale_root)
    stale_before = stale_service.state(session_id=SESSION, loop_id=stale_loop)
    with pytest.raises(ClaimLoopServiceError, match="prefix|revision"):
        stale_service.stage_protocol_factual_history(
            session_id=SESSION,
            loop_id=stale_loop,
            span=stale_span,
            idempotency_key="stage-factual-history-stale-revision-0001",
            expected_revision=stale_proposal["revision"] + 1,
        )
    with pytest.raises(ClaimLoopServiceError, match="proposal is stale"):
        _register(
            stale_service,
            stale_loop,
            {**stale_proposal, "proposal_sha256": "0" * 64},
            stale_stage,
        )
    stale_after = stale_service.state(session_id=SESSION, loop_id=stale_loop)
    assert stale_after.state_sha256 == stale_before.state_sha256
    assert stale_registry.effect_count() == 0


def test_protocol_adapters_and_deterministic_graph_never_touch_provider_or_key(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden_invoke(*args, **kwargs):
        raise AssertionError("provider-backed runner was invoked")

    original_getenv = multi_agent_module.os.getenv

    def guarded_getenv(name, default=None):
        if name == "OPENROUTER_API_KEY":
            raise AssertionError("provider credential was read")
        return original_getenv(name, default)

    monkeypatch.setattr(InstrumentedStructuredAgent, "invoke", forbidden_invoke)
    monkeypatch.setattr(multi_agent_module.os, "getenv", guarded_getenv)
    storage, service, registry, loop_id, _, proposal, staged, _ = (
        _prepare_ecab_registration(tmp_path)
    )
    result = _register(service, loop_id, proposal, staged)
    assert result["protocol_state"]["protocol_status"] == "replanned"
    assert registry.effect_count() == 1
    assert storage.model_calls() == []
    state = service.state(session_id=SESSION, loop_id=loop_id)
    assert state.incremental_loop_activity.model_calls == 0
    assert state.incremental_loop_activity.provider_calls == 0
    assert state.incremental_loop_activity.cost_usd == 0


def test_protocol_actual_plural_api_replays_exact_bytes(tmp_path: Path) -> None:
    storage = Storage(str(tmp_path / "casepath.db"))
    registry = LocalArtifactRegistryAdapterV1(tmp_path / "artifact-registry")
    source = _cycle_pipeline(storage)
    service = ClaimLoopService(
        storage,
        artifact_interpreter=DeterministicMouldArtifactInterpreter(),
        cycle_pipeline=_cycle_pipeline(storage),
        cycle_transport_mode="deterministic_test_double",
        source_pipeline=source,
        protocol_adapter=registry,
        correction_adapters={
            MouldNeutralAssessmentCorrectionAdapterV1.adapter_id: (
                MouldNeutralAssessmentCorrectionAdapterV1()
            )
        },
        clock=ManualClock(),
    )
    app = FastAPI()
    app.include_router(
        create_claim_loop_router(lambda: storage, service_getter=lambda: service)
    )
    client = TestClient(app)
    headers = {
        "X-CasePath-Session": SESSION,
        "X-CasePath-Idempotency-Key": "bootstrap-insurance-loop-0001",
    }
    bootstrap = client.post(
        "/api/claim-loops/v1/bootstrap/generated-mould", headers=headers
    )
    assert bootstrap.status_code == 200, bootstrap.content
    assert (
        client.post(
            "/api/claim-loops/v1/bootstrap/generated-mould", headers=headers
        ).content
        == bootstrap.content
    )
    loop_id = bootstrap.json()["loop_id"]
    read_headers = {"X-CasePath-Session": SESSION}
    proposal = client.get(
        f"/api/claim-loops/v1/{loop_id}/protocol/proposal",
        headers=read_headers,
    )
    assert proposal.status_code == 200, proposal.content
    proposal_value = proposal.json()
    stage_headers = {
        **read_headers,
        "X-CasePath-Idempotency-Key": "stage-neutral-assessment-0001",
    }
    stage = client.post(
        f"/api/claim-loops/v1/{loop_id}/protocol/sources/stage",
        headers=stage_headers,
        json={
            "filename": "neutral-assessment.txt",
            "media_type": "text/plain; charset=utf-8",
            "content": NEUTRAL_ASSESSMENT,
            "expected_revision": proposal_value["revision"],
        },
    )
    assert stage.status_code == 200, stage.content
    assert (
        client.post(
            f"/api/claim-loops/v1/{loop_id}/protocol/sources/stage",
            headers=stage_headers,
            json={
                "filename": "neutral-assessment.txt",
                "media_type": "text/plain; charset=utf-8",
                "content": NEUTRAL_ASSESSMENT,
                "expected_revision": proposal_value["revision"],
            },
        ).content
        == stage.content
    )
    register_headers = {
        **read_headers,
        "X-CasePath-Idempotency-Key": "register-neutral-assessment-0001",
    }
    register = client.post(
        f"/api/claim-loops/v1/{loop_id}/protocol/registrations",
        headers=register_headers,
        json={
            "proposal_sha256": proposal_value["proposal_sha256"],
            "staged_artifact_receipt_sha256": stage.json()[
                "staged_artifact_receipt_sha256"
            ],
            "expected_revision": proposal_value["revision"],
        },
    )
    assert register.status_code == 200, register.content
    assert register.json()["protocol_state"]["protocol_status"] == "replanned"
    protocol_state = client.get(
        f"/api/claim-loops/v1/{loop_id}/protocol-state",
        headers=read_headers,
    )
    assert protocol_state.status_code == 200
    assert (
        protocol_state.json()["projection_sha256"]
        == register.json()["protocol_state"]["projection_sha256"]
    )
    options = client.get(
        f"/api/claim-loops/v1/{loop_id}/protocol/corrections/options",
        headers=read_headers,
    )
    assert options.status_code == 200, options.content
    candidate = options.json()["candidates"][0]
    correction_headers = {
        **read_headers,
        "X-CasePath-Idempotency-Key": "prepare-selected-correction-api-0001",
    }
    assert (
        client.post(
            f"/api/claim-loops/v1/{loop_id}/protocol/corrections/proposal",
            headers=correction_headers,
        ).status_code
        == 422
    )
    tampered = {
        "candidate_sha256": "0" * 64,
        "target_assertion_sha256": candidate["target_assertion_sha256"],
        "target_interpretation_sha256": candidate[
            "target_interpretation_sha256"
        ],
        "semantic_delta_id": candidate["semantic_delta_id"],
        "expected_revision": candidate["revision"],
    }
    assert (
        client.post(
            f"/api/claim-loops/v1/{loop_id}/protocol/corrections/proposal",
            headers={
                **read_headers,
                "X-CasePath-Idempotency-Key": "prepare-tampered-correction-api-0001",
            },
            json=tampered,
        ).status_code
        == 409
    )
    selected = {
        "candidate_sha256": candidate["candidate_sha256"],
        "target_assertion_sha256": candidate["target_assertion_sha256"],
        "target_interpretation_sha256": candidate[
            "target_interpretation_sha256"
        ],
        "semantic_delta_id": candidate["semantic_delta_id"],
        "expected_revision": candidate["revision"],
    }
    assert (
        client.post(
            f"/api/claim-loops/v1/{loop_id}/protocol/corrections/proposal",
            headers={
                **read_headers,
                "X-CasePath-Idempotency-Key": "prepare-bool-revision-api-0001",
            },
            json={**selected, "expected_revision": True},
        ).status_code
        == 422
    )
    prepared = client.post(
        f"/api/claim-loops/v1/{loop_id}/protocol/corrections/proposal",
        headers=correction_headers,
        json=selected,
    )
    assert prepared.status_code == 200, prepared.content
    assert prepared.json()["selection"] == candidate
    assert (
        client.post(
            f"/api/claim-loops/v1/{loop_id}/protocol/corrections/proposal",
            headers=correction_headers,
            json=selected,
        ).content
        == prepared.content
    )
