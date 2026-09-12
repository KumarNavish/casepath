from __future__ import annotations

import ast
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
import threading
import time
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
import pytest

from casepath_api import langchain_runtime
from casepath_api.canonicalizer import MODEL_MODE_REFERENCE
from casepath_api.claim_loop import (
    ClaimLoopError,
    CorrectionToolResult,
    DEFAULT_EVIDENCE_TOOL_ID,
    DeterministicMouldArtifactInterpreter,
    SyntheticMouldEvidenceAdapter,
    ToolResult,
    ToolResultStatus,
    adapter_implementation_sha256_v1,
    reduce_claim_loop_event,
)
from casepath_api.claim_loop_cycle import (
    ClaimLoopCycleError,
    validate_accepted_role_artifacts_v1,
    validate_cycle_receipt_graph_binding_v1,
)
from casepath_api.claim_loop_contracts import (
    ClaimObservation,
    CorrectionEffect,
    SixAgentCycleReceipt,
    ToolArtifactReceipt,
    claim_loop_internal_event_key_v1,
)
from casepath_api.claim_loop_service import ClaimLoopService, ClaimLoopServiceError
from casepath_api.claim_loop_store import ClaimLoopStore, ClaimLoopStoreError
from casepath_api.claim_loop_router import create_claim_loop_router
from casepath_api.ecab_replay_adapter import (
    ECAB_FACTUAL_HISTORY_TOOL_ID,
    ECABReplayContractError,
    build_ecab_factual_history_span_v1,
    map_ecab_factual_history_span_v1,
)
from casepath_api.foundation.common import canonical_json_bytes, digest_text, digest_value
from casepath_api.multi_agent import (
    DeterministicStructuredAgent,
    NemotronMultiAgentOrchestrator,
    accepted_artifact_hash,
)
from casepath_api.pipeline_v15 import ClaimPipeline
from casepath_api.storage import Storage


SESSION = "claim-loop-test-session-0001"
CLAIM_ID = "DEF-027-E0-DEMO"
TEST_ADAPTER_SOURCE_SHA256 = digest_text(Path(__file__).read_text())


class ManualClock:
    def __init__(self) -> None:
        self._value = datetime(2026, 8, 28, 12, 0, tzinfo=timezone.utc)
        self._lock = threading.Lock()

    def __call__(self) -> str:
        with self._lock:
            value = self._value
            self._value += timedelta(milliseconds=1)
        return value.isoformat()

    def advance(self, *, seconds: int) -> None:
        with self._lock:
            self._value += timedelta(seconds=seconds)


class CountingUnavailableAdapter:
    adapter_id = DEFAULT_EVIDENCE_TOOL_ID
    implementation_id = "casepath.test-counting-unavailable-adapter/1.0.0"
    implementation_source_sha256 = TEST_ADAPTER_SOURCE_SHA256
    implementation_sha256 = adapter_implementation_sha256_v1(
        adapter_id=adapter_id,
        implementation_id=implementation_id,
        implementation_source_sha256=implementation_source_sha256,
    )

    def __init__(self, *, blocking: bool = False) -> None:
        self.calls = 0
        self._lock = threading.Lock()
        self.entered = threading.Event()
        self.release = threading.Event()
        if not blocking:
            self.release.set()

    def execute(self, **_: Any) -> ToolResult:
        with self._lock:
            self.calls += 1
        self.entered.set()
        if not self.release.wait(timeout=10):
            raise AssertionError("test adapter was not released")
        return ToolResult(
            status=ToolResultStatus.UNAVAILABLE,
            source_locator="synthetic-mould:test-unavailable",
            reason="deterministic fixture unavailable",
        )


class BlockingObservedAdapter(CountingUnavailableAdapter):
    implementation_id = "casepath.test-blocking-observed-adapter/1.0.0"
    implementation_sha256 = adapter_implementation_sha256_v1(
        adapter_id=CountingUnavailableAdapter.adapter_id,
        implementation_id=implementation_id,
        implementation_source_sha256=TEST_ADAPTER_SOURCE_SHA256,
    )

    def __init__(self) -> None:
        super().__init__(blocking=True)
        self._inner = SyntheticMouldEvidenceAdapter()

    def execute(self, **kwargs: Any) -> ToolResult:
        with self._lock:
            self.calls += 1
        self.entered.set()
        if not self.release.wait(timeout=10):
            raise AssertionError("test adapter was not released")
        return self._inner.execute(**kwargs)


class RaisingAdapter:
    adapter_id = DEFAULT_EVIDENCE_TOOL_ID
    implementation_id = "casepath.test-raising-adapter/1.0.0"
    implementation_source_sha256 = TEST_ADAPTER_SOURCE_SHA256
    implementation_sha256 = adapter_implementation_sha256_v1(
        adapter_id=adapter_id,
        implementation_id=implementation_id,
        implementation_source_sha256=implementation_source_sha256,
    )

    def __init__(self) -> None:
        self.calls = 0

    def execute(self, **_: Any) -> ToolResult:
        self.calls += 1
        raise RuntimeError("injected tool-process crash")


class SwitchableEvidenceAdapter:
    """One source-bound test adapter with explicit deterministic modes."""

    adapter_id = DEFAULT_EVIDENCE_TOOL_ID
    implementation_id = "casepath.test-switchable-evidence-adapter/1.0.0"
    implementation_source_sha256 = TEST_ADAPTER_SOURCE_SHA256
    implementation_sha256 = adapter_implementation_sha256_v1(
        adapter_id=adapter_id,
        implementation_id=implementation_id,
        implementation_source_sha256=implementation_source_sha256,
    )

    def __init__(self) -> None:
        self.calls = 0
        self.mode = "observed"
        self.entered = threading.Event()
        self.release = threading.Event()
        self.release.set()
        self._inner = SyntheticMouldEvidenceAdapter()

    def configure_observed(self) -> None:
        self.mode = "observed"
        self.entered.clear()
        self.release.set()

    def configure_unavailable(self, *, blocking: bool = False) -> None:
        self.mode = "unavailable"
        self.entered.clear()
        if blocking:
            self.release.clear()
        else:
            self.release.set()

    def configure_raise(self) -> None:
        self.mode = "raise"
        self.entered.clear()
        self.release.set()

    def execute(self, **kwargs: Any) -> ToolResult:
        self.calls += 1
        self.entered.set()
        if not self.release.wait(timeout=10):
            raise AssertionError("test adapter was not released")
        if self.mode == "raise":
            raise RuntimeError("injected tool-process crash")
        if self.mode == "observed":
            return self._inner.execute(**kwargs)
        return ToolResult(
            status=ToolResultStatus.UNAVAILABLE,
            source_locator="synthetic-mould:switchable-unavailable",
            reason="deterministic fixture unavailable",
        )


class StaticCorrectionAdapter:
    def __init__(self, effect: CorrectionEffect, *, adapter_id: str) -> None:
        self.effect = effect
        self.adapter_id = adapter_id

    def execute(self, **_: Any) -> CorrectionToolResult:
        return CorrectionToolResult(
            effect=self.effect,
            issuer_id=self.adapter_id,
            provenance_note="Server-owned deterministic correction fixture.",
        )


def _wait(storage: Storage, run_id: str) -> dict[str, Any]:
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


def _fixture(
    tmp_path: Path,
    *,
    adapter: object | None = None,
) -> tuple[Storage, ClaimLoopService, dict[str, Any], ManualClock]:
    storage = Storage(str(tmp_path / "claim-loop.db"))
    source = ClaimPipeline(
        storage,
        model_mode=MODEL_MODE_REFERENCE,
        pace_seconds=0,
    )
    run_id = source.create(CLAIM_ID, session_id=SESSION)
    _wait(storage, run_id)
    clock = ManualClock()
    adapters = (
        {DEFAULT_EVIDENCE_TOOL_ID: adapter}
        if adapter is not None
        else {}
    )
    service = ClaimLoopService(
        storage,
        adapters=adapters,
        artifact_interpreter=DeterministicMouldArtifactInterpreter(),
        cycle_pipeline=_cycle_pipeline(storage),
        cycle_transport_mode="deterministic_test_double",
        clock=clock,
    )
    created = service.create(
        session_id=SESSION,
        source_run_id=run_id,
        idempotency_key="create-loop-0001",
    )
    return storage, service, created, clock


def _claim_loop_test_client(
    *,
    storage: Storage,
    clock: ManualClock,
    adapters: dict[str, object],
    raise_server_exceptions: bool = True,
) -> TestClient:
    app = FastAPI()

    def service() -> ClaimLoopService:
        return ClaimLoopService(
            storage,
            adapters=adapters,
            artifact_interpreter=DeterministicMouldArtifactInterpreter(),
            cycle_pipeline=_cycle_pipeline(storage),
            cycle_transport_mode="deterministic_test_double",
            clock=clock,
        )

    app.include_router(
        create_claim_loop_router(lambda: storage, service_getter=service)
    )
    return TestClient(app, raise_server_exceptions=raise_server_exceptions)


def _bytes(value: dict[str, Any]) -> bytes:
    return canonical_json_bytes(value)


def _model_graph_audit(
    audit: dict[str, Any], *, missing_cost: bool = False
) -> dict[str, Any]:
    value = deepcopy(audit)
    value["transport_mode"] = "openrouter"
    value["model_assisted"] = True
    value["model"] = "nvidia/nemotron-3-ultra-550b-a55b-20260604"
    for index, agent in enumerate(value["agents"]):
        agent["actor_type"] = "nemotron_agent"
        agent["transport_mode"] = "openrouter"
        agent["model"] = value["model"]
        agent["provider"] = "DeepInfra"
        agent["call_count"] = 1
        agent["usage"] = (
            None
            if missing_cost and index == 0
            else {"actual_cost_usd": round((index + 1) / 1000, 8)}
        )
    return value


def _replace_source_run_audit(
    storage: Storage,
    *,
    run_id: str,
    audit: dict[str, Any],
    verification: dict[str, Any] | None = None,
) -> None:
    with storage.connect() as connection:
        row = connection.execute(
            "SELECT payload FROM runs WHERE run_id=? AND session_id=?",
            (run_id, SESSION),
        ).fetchone()
        assert row is not None
        payload = json.loads(row["payload"])
        payload["agent_orchestration"] = deepcopy(audit)
        payload["result"]["agent_orchestration"] = deepcopy(audit)
        if verification is not None:
            payload["verification"] = deepcopy(verification)
            payload["result"]["verification"] = deepcopy(verification)
        connection.execute(
            "UPDATE runs SET payload=? WHERE run_id=? AND session_id=?",
            (json.dumps(payload, ensure_ascii=False), run_id, SESSION),
        )


def _admit_correction(
    service: ClaimLoopService,
    *,
    session_id: str,
    loop_id: str,
    source_artifact_receipt_sha256: str,
    effect: CorrectionEffect,
    expires_at: str | None = None,
    suffix: str = "default",
):
    adapter_id = f"casepath.test-correction-authority.{suffix}"
    adapter = StaticCorrectionAdapter(
        effect, adapter_id=adapter_id
    )
    service.correction_adapters[adapter_id] = adapter
    service.store.correction_adapters[adapter_id] = adapter
    return service.register_correction(
        session_id=session_id,
        loop_id=loop_id,
        source_artifact_receipt_sha256=source_artifact_receipt_sha256,
        correction_adapter_id=adapter_id,
        expires_at=expires_at,
    )


def _advance_key(
    *,
    loop_id: str,
    idempotency_key: str,
    expected_revision: int | None,
    event_kind: str,
    adapter_id: str | None = None,
) -> str:
    request_sha256 = digest_value(
        {
            "expected_revision": expected_revision,
            "requested_adapter_id": adapter_id,
        }
    )
    return claim_loop_internal_event_key_v1(
        session_id=SESSION,
        loop_id=loop_id,
        client_idempotency_key=idempotency_key,
        request_type="advance",
        request_sha256=request_sha256,
        event_kind=event_kind,
    )


def _register_unavailable_acquisition(
    service: ClaimLoopService, state: Any, adapter: object
):
    result = ToolResult(
        status=ToolResultStatus.UNAVAILABLE,
        source_locator="synthetic-mould:test-unavailable",
        reason="deterministic fixture unavailable",
    )
    return service._register_acquisition_result(
        state=state,
        adapter=adapter,
        result=result,
        timestamp=service._clock(),
    )


def _register_observed_artifact(
    service: ClaimLoopService,
    state: Any,
    result: ToolResult,
    *,
    timestamp: str,
) -> ToolArtifactReceipt:
    adapter = service.adapters[DEFAULT_EVIDENCE_TOOL_ID]
    acquisition = service._register_acquisition_result(
        state=state,
        adapter=adapter,
        result=result,
        timestamp=timestamp,
    )
    return service._register_tool_result(state=state, acquisition=acquisition)


def _tool_artifact_from_payload(payload: dict[str, Any]) -> ToolArtifactReceipt:
    value = deepcopy(payload)
    observation = value["observation"]
    observation_payload = {
        key: item
        for key, item in observation.items()
        if key != "observation_sha256"
    }
    observation["observation_sha256"] = digest_value(observation_payload)
    ClaimObservation.model_validate(observation)
    interpretation = value["interpretation"]
    interpretation["action_id"] = value["action_id"]
    interpretation["action_sha256"] = value["action_sha256"]
    interpretation["raw_artifact_sha256"] = value["raw_artifact_sha256"]
    interpretation["acquisition_receipt_sha256"] = value[
        "acquisition_receipt_sha256"
    ]
    interpretation["observation"] = deepcopy(observation)
    interpretation_payload = {
        key: item
        for key, item in interpretation.items()
        if key != "receipt_sha256"
    }
    interpretation["receipt_sha256"] = digest_value(interpretation_payload)
    receipt_payload = {
        key: item for key, item in value.items() if key != "receipt_sha256"
    }
    value["receipt_sha256"] = digest_value(receipt_payload)
    return ToolArtifactReceipt.model_validate(value)


def _server_interpreted_tool_payload(
    *,
    service: ClaimLoopService,
    state: Any,
    result: ToolResult,
    timestamp: str,
) -> dict[str, Any]:
    action = state.selected_action
    assert action is not None
    assert state.active_dispatch_sha256 is not None
    assert result.sanitized_content is not None
    assert result.artifact_source_version is not None
    assert result.artifact_page_count == 1
    adapter = service.adapters[DEFAULT_EVIDENCE_TOOL_ID]
    acquisition = service._register_acquisition_result(
        state=state,
        adapter=adapter,
        result=result,
        timestamp=timestamp,
    )
    assert service.artifact_interpreter is not None
    interpretation = service.artifact_interpreter.interpret(
        action=action,
        state=state,
        acquisition=acquisition,
    )
    return {
        "contract": "casepath.tool-artifact-receipt/1.1.0",
        "session_id": state.session_id,
        "loop_id": state.loop_id,
        "action_id": action.action_id,
        "action_sha256": action.action_sha256,
        "dispatch_sha256": state.active_dispatch_sha256,
        "adapter_id": DEFAULT_EVIDENCE_TOOL_ID,
        "acquisition_receipt_sha256": acquisition.receipt_sha256,
        "acquisition_receipt": acquisition.model_dump(mode="json"),
        "artifact_source_version": result.artifact_source_version,
        "artifact_page_count": result.artifact_page_count,
        "sanitized_content": result.sanitized_content,
        "raw_artifact_sha256": acquisition.receipt_sha256,
        "interpretation": interpretation.model_dump(mode="json"),
        "observation": interpretation.observation.model_dump(mode="json"),
        "registered_at": timestamp,
        "model_calls": 0,
        "provider_calls": 0,
        "provider_credentials_read": False,
        "cost_usd": 0.0,
    }


def test_completed_advance_replay_is_exact_after_later_tail(
    tmp_path: Path,
) -> None:
    adapter = SwitchableEvidenceAdapter()
    _, service, created, _ = _fixture(tmp_path, adapter=adapter)
    loop_id = created["loop_id"]

    first = service.advance(
        session_id=SESSION,
        loop_id=loop_id,
        idempotency_key="advance-first-0001",
        expected_revision=created["revision"],
    )
    assert first["command_receipt"]["idempotency_key"] == _advance_key(
        loop_id=loop_id,
        idempotency_key="advance-first-0001",
        expected_revision=created["revision"],
        event_kind="result",
    )
    first_bytes = _bytes(first)
    adapter.configure_unavailable()
    later = service.advance(
        session_id=SESSION,
        loop_id=loop_id,
        idempotency_key="advance-later-0002",
        expected_revision=first["revision"],
    )
    assert later["revision"] > first["revision"]

    replay = service.advance(
        session_id=SESSION,
        loop_id=loop_id,
        idempotency_key="advance-first-0001",
        expected_revision=created["revision"],
    )

    assert _bytes(replay) == first_bytes
    assert service.state(session_id=SESSION, loop_id=loop_id).revision == later[
        "revision"
    ]
    with service.store.connect() as connection:
        statuses = {
            row["status"]
            for row in connection.execute(
                """SELECT status FROM claim_loop_client_requests
                WHERE session_id=? AND loop_id=?""",
                (SESSION, loop_id),
            )
        }
    assert statuses == {"COMPLETED"}


def test_noop_client_response_is_exact_after_tail_advances(
    tmp_path: Path,
) -> None:
    adapter = CountingUnavailableAdapter()
    _, service, created, _ = _fixture(tmp_path, adapter=adapter)
    loop_id = created["loop_id"]
    selected = service.select_action(
        session_id=SESSION,
        loop_id=loop_id,
        idempotency_key="select-initial-0001",
        expected_revision=created["revision"],
    )
    noop = service.select_action(
        session_id=SESSION,
        loop_id=loop_id,
        idempotency_key="select-noop-0002",
        expected_revision=selected["revision"],
    )
    assert noop["command_receipt"] is None
    tail = service.advance(
        session_id=SESSION,
        loop_id=loop_id,
        idempotency_key="advance-tail-0003",
        expected_revision=selected["revision"],
    )
    assert tail["revision"] > noop["revision"]

    replay = service.select_action(
        session_id=SESSION,
        loop_id=loop_id,
        idempotency_key="select-noop-0002",
        expected_revision=selected["revision"],
    )

    assert _bytes(replay) == _bytes(noop)
    assert adapter.calls == 1


def test_noop_reservation_recovers_original_prefix_after_precompletion_crash(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = CountingUnavailableAdapter()
    _, service, created, _ = _fixture(tmp_path, adapter=adapter)
    loop_id = created["loop_id"]
    selected = service.select_action(
        session_id=SESSION,
        loop_id=loop_id,
        idempotency_key="noop-crash-select-0001",
        expected_revision=created["revision"],
    )
    reserved_response = service._response(
        service.state(session_id=SESSION, loop_id=loop_id), None
    )
    original_complete = service.store.complete_client_request
    crashed = False

    def crash_before_completion(**kwargs: Any) -> dict[str, Any]:
        nonlocal crashed
        if (
            kwargs.get("idempotency_key") == "noop-crash-reserved-0002"
            and not crashed
        ):
            crashed = True
            raise RuntimeError("injected no-op completion crash")
        return original_complete(**kwargs)

    monkeypatch.setattr(
        service.store, "complete_client_request", crash_before_completion
    )
    with pytest.raises(RuntimeError, match="no-op completion crash"):
        service.select_action(
            session_id=SESSION,
            loop_id=loop_id,
            idempotency_key="noop-crash-reserved-0002",
            expected_revision=selected["revision"],
        )
    monkeypatch.setattr(
        service.store, "complete_client_request", original_complete
    )

    later = service.advance(
        session_id=SESSION,
        loop_id=loop_id,
        idempotency_key="noop-crash-tail-0003",
        expected_revision=selected["revision"],
    )
    assert later["revision"] > reserved_response["revision"]
    recovered = service.select_action(
        session_id=SESSION,
        loop_id=loop_id,
        idempotency_key="noop-crash-reserved-0002",
        expected_revision=selected["revision"],
    )
    replay = service.select_action(
        session_id=SESSION,
        loop_id=loop_id,
        idempotency_key="noop-crash-reserved-0002",
        expected_revision=selected["revision"],
    )

    assert _bytes(recovered) == _bytes(reserved_response)
    assert _bytes(replay) == _bytes(reserved_response)
    assert service.state(session_id=SESSION, loop_id=loop_id).revision == later[
        "revision"
    ]


def test_abandoned_mutating_reservation_never_masquerades_as_noop(
    tmp_path: Path,
) -> None:
    adapter = SyntheticMouldEvidenceAdapter()
    _, service, created, _ = _fixture(tmp_path, adapter=adapter)
    loop_id = created["loop_id"]
    request = {"expected_revision": None, "requested_adapter_id": None}
    service._bind_client_request(
        session_id=SESSION,
        loop_id=loop_id,
        idempotency_key="abandoned-mutating-0001",
        request_type="advance",
        request=request,
    )
    service.select_action(
        session_id=SESSION,
        loop_id=loop_id,
        idempotency_key="abandoned-tail-select-0002",
        expected_revision=created["revision"],
    )

    errors: list[str] = []
    for _ in range(2):
        with pytest.raises(
            ClaimLoopServiceError, match="reservation prefix changed"
        ) as exc_info:
            service.advance(
                session_id=SESSION,
                loop_id=loop_id,
                idempotency_key="abandoned-mutating-0001",
            )
        errors.append(str(exc_info.value))
    binding = service.store.client_request(
        session_id=SESSION,
        loop_id=loop_id,
        idempotency_key="abandoned-mutating-0001",
        request_type="advance",
        request_sha256=digest_value(request),
    )
    assert errors[0] == errors[1]
    assert binding["status"] == "SUPERSEDED"
    assert binding["response"] is None
    assert binding["failure"]["state_sha256"] == created["state_sha256"]


def test_abandoned_select_reservation_never_targets_a_later_state(
    tmp_path: Path,
) -> None:
    adapter = SyntheticMouldEvidenceAdapter()
    _, service, created, _ = _fixture(tmp_path, adapter=adapter)
    loop_id = created["loop_id"]
    request = {"expected_revision": None}
    service._bind_client_request(
        session_id=SESSION,
        loop_id=loop_id,
        idempotency_key="abandoned-select-0001",
        request_type="select_action",
        request=request,
    )
    service.advance(
        session_id=SESSION,
        loop_id=loop_id,
        idempotency_key="abandoned-select-tail-0002",
    )
    event_count = len(
        service.store.events(session_id=SESSION, loop_id=loop_id)
    )

    for _ in range(2):
        with pytest.raises(
            ClaimLoopServiceError, match="select reservation prefix changed"
        ):
            service.select_action(
                session_id=SESSION,
                loop_id=loop_id,
                idempotency_key="abandoned-select-0001",
            )
    assert len(
        service.store.events(session_id=SESSION, loop_id=loop_id)
    ) == event_count


def _assert_stable_superseded_request(
    *,
    service: ClaimLoopService,
    loop_id: str,
    idempotency_key: str,
    request_type: str,
    request: dict[str, Any],
    retry: Any,
) -> None:
    envelopes: list[dict[str, Any]] = []
    for _ in range(2):
        with pytest.raises(
            ClaimLoopServiceError, match="reservation prefix changed"
        ) as exc_info:
            retry()
        assert exc_info.value.conflict_envelope is not None
        envelopes.append(exc_info.value.conflict_envelope)
    assert _bytes(envelopes[0]) == _bytes(envelopes[1])
    assert envelopes[0]["failure_sha256"] == digest_value(
        {
            key: value
            for key, value in envelopes[0].items()
            if key != "failure_sha256"
        }
    )
    binding = service.store.client_request(
        session_id=SESSION,
        loop_id=loop_id,
        idempotency_key=idempotency_key,
        request_type=request_type,
        request_sha256=digest_value(request),
    )
    assert binding["status"] == "SUPERSEDED"
    assert binding["response"] is None
    assert _bytes(binding["failure"]) == _bytes(envelopes[0])


def test_abandoned_tool_unavailable_request_terminalizes_after_tail_drift(
    tmp_path: Path,
) -> None:
    adapter = RaisingAdapter()
    _, service, created, _ = _fixture(tmp_path, adapter=adapter)
    loop_id = created["loop_id"]
    with pytest.raises(RuntimeError, match="tool-process crash"):
        service.advance(
            session_id=SESSION,
            loop_id=loop_id,
            idempotency_key="unavailable-dispatch-owner-0001",
            expected_revision=created["revision"],
        )
    active = service._raw_state(session_id=SESSION, loop_id=loop_id)
    assert active.selected_action is not None
    assert active.active_dispatch_sha256 is not None
    acquisition = _register_unavailable_acquisition(service, active, adapter)
    request = {
        "action_id": active.selected_action.action_id,
        "outcome": "unavailable",
        "dispatch_sha256": active.active_dispatch_sha256,
        "acquisition_receipt_sha256": acquisition.receipt_sha256,
        "advance_request_sha256": None,
    }
    old_key = "abandoned-unavailable-0002"
    service._bind_client_request(
        session_id=SESSION,
        loop_id=loop_id,
        idempotency_key=old_key,
        request_type="tool_unavailable",
        request=request,
    )
    service.state(session_id=SESSION, loop_id=loop_id)

    _assert_stable_superseded_request(
        service=service,
        loop_id=loop_id,
        idempotency_key=old_key,
        request_type="tool_unavailable",
        request=request,
        retry=lambda: service.tool_unavailable(
            session_id=SESSION,
            loop_id=loop_id,
            action_id=active.selected_action.action_id,
            outcome="unavailable",
            idempotency_key=old_key,
            dispatch_sha256=active.active_dispatch_sha256,
            acquisition_receipt_sha256=acquisition.receipt_sha256,
        ),
    )


def test_abandoned_apply_correction_terminalizes_after_tail_drift(
    tmp_path: Path,
) -> None:
    _, service, created, _ = _fixture(
        tmp_path, adapter=SyntheticMouldEvidenceAdapter()
    )
    loop_id = created["loop_id"]
    service.advance(
        session_id=SESSION,
        loop_id=loop_id,
        idempotency_key="abandoned-apply-source-0001",
        expected_revision=created["revision"],
    )
    state = service.state(session_id=SESSION, loop_id=loop_id)
    artifact = service.store.tool_artifact(
        state.projection_ledger[0].artifact_receipt_sha256
    )
    assert artifact is not None
    correction = _admit_correction(
        service,
        session_id=SESSION,
        loop_id=loop_id,
        source_artifact_receipt_sha256=artifact.receipt_sha256,
        effect=CorrectionEffect(
            fact_id=artifact.observation.fact_id,
            evidence_item_id=artifact.observation.evidence_item_id,
            value=artifact.observation.source_refs[0].sanitized_excerpt,
            fact_state="conflicting",
            normalized_value=None,
            explanation="Retract the prior interpretation under exact authority.",
            evidence_status="provided_sufficient",
        ),
        suffix="abandoned-apply",
    )
    request = {"correction_id": correction.correction_id}
    old_key = "abandoned-apply-0002"
    service._bind_client_request(
        session_id=SESSION,
        loop_id=loop_id,
        idempotency_key=old_key,
        request_type="apply_correction",
        request=request,
    )
    service.apply_correction(
        session_id=SESSION,
        loop_id=loop_id,
        correction_id=correction.correction_id,
        idempotency_key="winning-apply-0003",
    )

    _assert_stable_superseded_request(
        service=service,
        loop_id=loop_id,
        idempotency_key=old_key,
        request_type="apply_correction",
        request=request,
        retry=lambda: service.apply_correction(
            session_id=SESSION,
            loop_id=loop_id,
            correction_id=correction.correction_id,
            idempotency_key=old_key,
        ),
    )


def test_crash_after_result_event_recovers_original_client_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = CountingUnavailableAdapter()
    storage, service, created, clock = _fixture(tmp_path, adapter=adapter)
    loop_id = created["loop_id"]
    original_write = service.store._write_checkpoint
    crashed = False

    def crash_once(**kwargs: Any) -> None:
        nonlocal crashed
        if (
            not crashed
            and service.store.idempotent_event(
                session_id=SESSION,
                loop_id=loop_id,
                idempotency_key=_advance_key(
                    loop_id=loop_id,
                    idempotency_key="advance-crash-0001",
                    expected_revision=created["revision"],
                    event_kind="result",
                ),
            )
            is not None
        ):
            crashed = True
            raise RuntimeError("injected post-event crash")
        original_write(**kwargs)

    monkeypatch.setattr(service.store, "_write_checkpoint", crash_once)
    with pytest.raises(RuntimeError, match="injected post-event crash"):
        service.advance(
            session_id=SESSION,
            loop_id=loop_id,
            idempotency_key="advance-crash-0001",
            expected_revision=created["revision"],
        )
    assert adapter.calls == 1
    monkeypatch.setattr(service.store, "_write_checkpoint", original_write)

    restarted = ClaimLoopService(
        storage,
        adapters={DEFAULT_EVIDENCE_TOOL_ID: adapter},
        cycle_pipeline=_cycle_pipeline(storage),
        cycle_transport_mode="deterministic_test_double",
        clock=clock,
    )
    recovered = restarted.advance(
        session_id=SESSION,
        loop_id=loop_id,
        idempotency_key="advance-crash-0001",
        expected_revision=created["revision"],
    )
    replay = restarted.advance(
        session_id=SESSION,
        loop_id=loop_id,
        idempotency_key="advance-crash-0001",
        expected_revision=created["revision"],
    )

    assert recovered["command_receipt"]["idempotency_key"] == _advance_key(
        loop_id=loop_id,
        idempotency_key="advance-crash-0001",
        expected_revision=created["revision"],
        event_kind="result",
    )
    assert _bytes(replay) == _bytes(recovered)
    assert adapter.calls == 1


def test_idempotency_key_is_global_across_routes(tmp_path: Path) -> None:
    adapter = CountingUnavailableAdapter()
    _, service, created, _ = _fixture(tmp_path, adapter=adapter)
    loop_id = created["loop_id"]
    service.select_action(
        session_id=SESSION,
        loop_id=loop_id,
        idempotency_key="shared-client-key-0001",
        expected_revision=created["revision"],
    )

    with pytest.raises(ClaimLoopServiceError, match="different client request"):
        service.advance(
            session_id=SESSION,
            loop_id=loop_id,
            idempotency_key="shared-client-key-0001",
            expected_revision=created["revision"],
        )
    assert adapter.calls == 0


def test_create_key_is_session_scoped_and_replay_is_exact_after_tail(
    tmp_path: Path,
) -> None:
    adapter = CountingUnavailableAdapter()
    storage, service, created, _ = _fixture(tmp_path, adapter=adapter)
    original = _bytes(created)
    source = ClaimPipeline(
        storage,
        model_mode=MODEL_MODE_REFERENCE,
        pace_seconds=0,
    )
    second_run_id = source.create(CLAIM_ID, session_id=SESSION)
    _wait(storage, second_run_id)

    with pytest.raises(ClaimLoopServiceError, match="different client request"):
        service.create(
            session_id=SESSION,
            source_run_id=second_run_id,
            idempotency_key="create-loop-0001",
        )
    assert len(
        [
            event
            for event in service.store.events(
                session_id=SESSION, loop_id=created["loop_id"]
            )
            if event.event_type == "LOOP_CREATED"
        ]
    ) == 1

    service.advance(
        session_id=SESSION,
        loop_id=created["loop_id"],
        idempotency_key="advance-after-create-0001",
        expected_revision=created["revision"],
    )
    replay = service.create(
        session_id=SESSION,
        source_run_id=service.state(
            session_id=SESSION, loop_id=created["loop_id"]
        ).source_run_id,
        idempotency_key="create-loop-0001",
    )
    assert _bytes(replay) == original


def test_create_recovers_event_committed_before_result_binding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    storage = Storage(str(tmp_path / "claim-loop.db"))
    source = ClaimPipeline(storage, model_mode=MODEL_MODE_REFERENCE, pace_seconds=0)
    run_id = source.create(CLAIM_ID, session_id=SESSION)
    _wait(storage, run_id)
    clock = ManualClock()
    service = ClaimLoopService(
        storage,
        cycle_pipeline=_cycle_pipeline(storage),
        cycle_transport_mode="deterministic_test_double",
        clock=clock,
    )
    original_complete = service.store.complete_client_request
    crashed = False

    def crash_once(**kwargs: Any) -> dict[str, Any]:
        nonlocal crashed
        if kwargs.get("request_type") == "create" and not crashed:
            crashed = True
            raise RuntimeError("injected create result-binding crash")
        return original_complete(**kwargs)

    monkeypatch.setattr(service.store, "complete_client_request", crash_once)
    with pytest.raises(RuntimeError, match="result-binding crash"):
        service.create(
            session_id=SESSION,
            source_run_id=run_id,
            idempotency_key="create-crash-0001",
        )
    monkeypatch.setattr(service.store, "complete_client_request", original_complete)

    recovered = service.create(
        session_id=SESSION,
        source_run_id=run_id,
        idempotency_key="create-crash-0001",
    )
    assert recovered["revision"] == 1
    assert len(
        service.store.events(session_id=SESSION, loop_id=recovered["loop_id"])
    ) == 1


@pytest.mark.parametrize("legacy_suffix", ["select", "dispatch", "result"])
def test_legacy_derived_key_prepoison_cannot_bypass_revision_cas(
    tmp_path: Path, legacy_suffix: str
) -> None:
    adapter = CountingUnavailableAdapter()
    _, service, created, _ = _fixture(
        tmp_path / legacy_suffix, adapter=adapter
    )
    loop_id = created["loop_id"]
    parent_key = "victim-advance-0001"
    service.select_action(
        session_id=SESSION,
        loop_id=loop_id,
        idempotency_key=f"{parent_key}:{legacy_suffix}",
        expected_revision=created["revision"],
    )

    with pytest.raises(ClaimLoopServiceError, match="revision changed"):
        service.advance(
            session_id=SESSION,
            loop_id=loop_id,
            idempotency_key=parent_key,
            expected_revision=created["revision"],
        )
    assert adapter.calls == 0


def test_distinct_default_advance_keys_never_share_internal_events(
    tmp_path: Path,
) -> None:
    adapter = SyntheticMouldEvidenceAdapter()
    _, service, created, _ = _fixture(tmp_path, adapter=adapter)
    loop_id = created["loop_id"]
    first = service.advance(
        session_id=SESSION,
        loop_id=loop_id,
        idempotency_key="advance-default-a-0001",
    )
    second = service.advance(
        session_id=SESSION,
        loop_id=loop_id,
        idempotency_key="advance-default-b-0002",
    )

    assert second["revision"] > first["revision"]
    assert first["command_receipt"]["idempotency_key"] != second[
        "command_receipt"
    ]["idempotency_key"]
    assert len(
        service.state(session_id=SESSION, loop_id=loop_id).action_history
    ) == 2


@pytest.mark.parametrize(
    "damage",
    ["deleted", "bad_json", "stale_prefix", "bad_revision", "bad_event", "bad_state"],
)
def test_checkpoint_is_fully_rebuilt_from_valid_journal(
    tmp_path: Path, damage: str
) -> None:
    _, service, created, clock = _fixture(
        tmp_path / damage, adapter=SyntheticMouldEvidenceAdapter()
    )
    loop_id = created["loop_id"]
    service.advance(
        session_id=SESSION,
        loop_id=loop_id,
        idempotency_key=f"advance-before-checkpoint-{damage}",
        expected_revision=created["revision"],
    )
    authoritative = service.store.snapshot(
        session_id=SESSION, loop_id=loop_id
    )[0]
    with service.store.connect() as connection:
        if damage == "deleted":
            connection.execute(
                "DELETE FROM claim_loop_checkpoints WHERE session_id=? AND loop_id=?",
                (SESSION, loop_id),
            )
        elif damage == "bad_json":
            connection.execute(
                "UPDATE claim_loop_checkpoints SET state_json='{' WHERE session_id=? AND loop_id=?",
                (SESSION, loop_id),
            )
        elif damage == "stale_prefix":
            rows = service.store._event_rows(connection, SESSION, loop_id)
            prefix = service.store._replay_rows(
                rows[:1], session_id=SESSION, loop_id=loop_id
            )
            connection.execute(
                """UPDATE claim_loop_checkpoints SET revision=?,last_event_sha256=?,
                state_sha256=?,state_json=? WHERE session_id=? AND loop_id=?""",
                (
                    prefix.revision,
                    prefix.last_event_sha256,
                    prefix.state_sha256,
                    canonical_json_bytes(prefix.model_dump(mode="json")).decode(),
                    SESSION,
                    loop_id,
                ),
            )
        elif damage == "bad_revision":
            connection.execute(
                "UPDATE claim_loop_checkpoints SET revision=-7 WHERE session_id=? AND loop_id=?",
                (SESSION, loop_id),
            )
        elif damage == "bad_event":
            connection.execute(
                "UPDATE claim_loop_checkpoints SET last_event_sha256=? WHERE session_id=? AND loop_id=?",
                ("0" * 64, SESSION, loop_id),
            )
        else:
            connection.execute(
                "UPDATE claim_loop_checkpoints SET state_sha256=? WHERE session_id=? AND loop_id=?",
                ("f" * 64, SESSION, loop_id),
            )

    repaired = service.store.recover(
        session_id=SESSION, loop_id=loop_id, timestamp=clock()
    )
    assert repaired == authoritative
    with service.store.connect() as connection:
        row = connection.execute(
            "SELECT * FROM claim_loop_checkpoints WHERE session_id=? AND loop_id=?",
            (SESSION, loop_id),
        ).fetchone()
    assert row["revision"] == authoritative.revision
    assert row["last_event_sha256"] == authoritative.last_event_sha256
    assert row["state_sha256"] == authoritative.state_sha256
    assert __import__("json").loads(row["state_json"]) == (
        authoritative.model_dump(mode="json")
    )


def test_event_chain_corruption_is_never_masked_by_checkpoint_repair(
    tmp_path: Path,
) -> None:
    _, service, created, clock = _fixture(tmp_path)
    loop_id = created["loop_id"]
    with service.store.connect() as connection:
        connection.execute(
            """UPDATE claim_loop_events SET command_sha256=?
            WHERE session_id=? AND loop_id=? AND sequence=1""",
            ("0" * 64, SESSION, loop_id),
        )
    with pytest.raises(ClaimLoopStoreError, match="event chain diverged"):
        service.store.recover(
            session_id=SESSION, loop_id=loop_id, timestamp=clock()
        )


def test_resulting_state_hash_corruption_fails_full_journal_replay(
    tmp_path: Path,
) -> None:
    _, service, created, clock = _fixture(tmp_path)
    loop_id = created["loop_id"]
    with service.store.connect() as connection:
        row = connection.execute(
            """SELECT event_json FROM claim_loop_events
            WHERE session_id=? AND loop_id=? AND sequence=1""",
            (SESSION, loop_id),
        ).fetchone()
        event = json.loads(row["event_json"])
        event["resulting_state_sha256"] = "f" * 64
        connection.execute(
            """UPDATE claim_loop_events SET event_json=?
            WHERE session_id=? AND loop_id=? AND sequence=1""",
            (
                canonical_json_bytes(event).decode(),
                SESSION,
                loop_id,
            ),
        )
    with pytest.raises(ClaimLoopStoreError, match="event result"):
        service.store.recover(
            session_id=SESSION, loop_id=loop_id, timestamp=clock()
        )


def test_concurrent_identical_advance_executes_adapter_once(
    tmp_path: Path,
) -> None:
    adapter = CountingUnavailableAdapter(blocking=True)
    storage, service_a, created, clock = _fixture(tmp_path, adapter=adapter)
    loop_id = created["loop_id"]
    selected = service_a.select_action(
        session_id=SESSION,
        loop_id=loop_id,
        idempotency_key="preselect-0001",
        expected_revision=created["revision"],
    )
    service_b = ClaimLoopService(
        storage,
        adapters={DEFAULT_EVIDENCE_TOOL_ID: adapter},
        cycle_pipeline=_cycle_pipeline(storage),
        cycle_transport_mode="deterministic_test_double",
        clock=clock,
    )
    results: list[dict[str, Any]] = []
    errors: list[BaseException] = []

    def invoke(service: ClaimLoopService) -> None:
        try:
            results.append(
                service.advance(
                    session_id=SESSION,
                    loop_id=loop_id,
                    idempotency_key="concurrent-advance-0001",
                    expected_revision=selected["revision"],
                )
            )
        except BaseException as exc:  # pragma: no cover - asserted below
            errors.append(exc)

    thread_a = threading.Thread(target=invoke, args=(service_a,))
    thread_b = threading.Thread(target=invoke, args=(service_b,))
    thread_a.start()
    assert adapter.entered.wait(timeout=5)
    thread_b.start()
    time.sleep(0.05)
    adapter.release.set()
    thread_a.join(timeout=10)
    thread_b.join(timeout=10)

    assert errors == []
    assert len(results) == 2
    assert _bytes(results[0]) == _bytes(results[1])
    assert adapter.calls == 1
    keys = [
        event.idempotency_key
        for event in service_a.store.events(session_id=SESSION, loop_id=loop_id)
    ]
    assert keys.count(
        _advance_key(
            loop_id=loop_id,
            idempotency_key="concurrent-advance-0001",
            expected_revision=selected["revision"],
            event_kind="dispatch",
        )
    ) == 1
    assert keys.count(
        _advance_key(
            loop_id=loop_id,
            idempotency_key="concurrent-advance-0001",
            expected_revision=selected["revision"],
            event_kind="result",
        )
    ) == 1


def test_concurrent_noop_bookkeeping_does_not_break_active_dispatch(
    tmp_path: Path,
) -> None:
    adapter = BlockingObservedAdapter()
    storage, service_a, created, clock = _fixture(tmp_path, adapter=adapter)
    loop_id = created["loop_id"]
    service_b = ClaimLoopService(
        storage,
        adapters={DEFAULT_EVIDENCE_TOOL_ID: adapter},
        cycle_pipeline=_cycle_pipeline(storage),
        cycle_transport_mode="deterministic_test_double",
        clock=clock,
    )
    result_a: list[dict[str, Any]] = []
    errors: list[BaseException] = []

    def run_dispatch() -> None:
        try:
            result_a.append(
                service_a.advance(
                    session_id=SESSION,
                    loop_id=loop_id,
                    idempotency_key="blocked-dispatch-a-0001",
                    expected_revision=created["revision"],
                )
            )
        except BaseException as exc:  # pragma: no cover - asserted below
            errors.append(exc)

    thread = threading.Thread(target=run_dispatch)
    thread.start()
    assert adapter.entered.wait(timeout=5)
    dispatch_revision = service_b.state(
        session_id=SESSION, loop_id=loop_id
    ).revision
    noop = service_b.advance(
        session_id=SESSION,
        loop_id=loop_id,
        idempotency_key="blocked-dispatch-b-0002",
        expected_revision=dispatch_revision,
    )
    assert noop["revision"] == dispatch_revision
    assert noop["command_receipt"] is None
    assert service_b.state(session_id=SESSION, loop_id=loop_id).revision == (
        dispatch_revision
    )

    adapter.release.set()
    thread.join(timeout=10)
    assert errors == []
    assert len(result_a) == 1
    assert result_a[0]["revision"] > dispatch_revision
    assert adapter.calls == 1
    replay = service_b.advance(
        session_id=SESSION,
        loop_id=loop_id,
        idempotency_key="blocked-dispatch-b-0002",
        expected_revision=dispatch_revision,
    )
    assert _bytes(replay) == _bytes(noop)


def test_post_select_crash_cannot_cross_into_newer_action_lineage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = SyntheticMouldEvidenceAdapter()
    _, service, created, _ = _fixture(tmp_path, adapter=adapter)
    loop_id = created["loop_id"]
    original_append = service.store.append
    crashed = False

    def crash_before_dispatch(**kwargs: Any):
        nonlocal crashed
        if (
            kwargs.get("event_type") == "ACTION_DISPATCH_STARTED"
            and kwargs.get("command", {}).get("client_idempotency_key")
            == "post-select-a-0001"
            and not crashed
        ):
            crashed = True
            raise RuntimeError("injected post-select crash")
        return original_append(**kwargs)

    monkeypatch.setattr(service.store, "append", crash_before_dispatch)
    with pytest.raises(RuntimeError, match="post-select crash"):
        service.advance(
            session_id=SESSION,
            loop_id=loop_id,
            idempotency_key="post-select-a-0001",
            expected_revision=created["revision"],
        )
    monkeypatch.setattr(service.store, "append", original_append)
    selected_event = next(
        event
        for event in service.store.events(session_id=SESSION, loop_id=loop_id)
        if event.idempotency_key
        == _advance_key(
            loop_id=loop_id,
            idempotency_key="post-select-a-0001",
            expected_revision=created["revision"],
            event_kind="select",
        )
    )
    selected_action_id = selected_event.command["selected_action_id"]

    consumed = service.advance(
        session_id=SESSION,
        loop_id=loop_id,
        idempotency_key="post-select-b-0002",
    )
    assert consumed["selected_action"]["action_id"] != selected_action_id
    action_history_count = len(
        service.state(session_id=SESSION, loop_id=loop_id).action_history
    )
    recovered_a = service.advance(
        session_id=SESSION,
        loop_id=loop_id,
        idempotency_key="post-select-a-0001",
        expected_revision=created["revision"],
    )

    assert recovered_a["selected_action"]["action_id"] == selected_action_id
    assert recovered_a["revision"] == selected_event.sequence
    assert len(
        service.state(session_id=SESSION, loop_id=loop_id).action_history
    ) == action_history_count


def test_refreshed_dispatch_generation_rejects_stale_worker(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = CountingUnavailableAdapter()
    storage, service_a, created, clock = _fixture(tmp_path, adapter=adapter)
    loop_id = created["loop_id"]
    selected = service_a.select_action(
        session_id=SESSION,
        loop_id=loop_id,
        idempotency_key="generation-preselect-0001",
        expected_revision=created["revision"],
    )
    service_b = ClaimLoopService(
        storage,
        adapters={DEFAULT_EVIDENCE_TOOL_ID: adapter},
        cycle_pipeline=_cycle_pipeline(storage),
        cycle_transport_mode="deterministic_test_double",
        clock=clock,
    )
    stale_ready = threading.Event()
    resume_stale = threading.Event()
    original_append = service_a.store.append

    def stall_dispatch(**kwargs: Any):
        if kwargs.get("event_type") == "ACTION_DISPATCH_STARTED":
            stale_ready.set()
            assert resume_stale.wait(timeout=10)
        return original_append(**kwargs)

    monkeypatch.setattr(service_a.store, "append", stall_dispatch)
    errors: list[BaseException] = []

    def stale_worker() -> None:
        try:
            service_a.advance(
                session_id=SESSION,
                loop_id=loop_id,
                idempotency_key="generation-race-0001",
                expected_revision=selected["revision"],
            )
        except BaseException as exc:  # pragma: no cover - asserted below
            errors.append(exc)

    thread = threading.Thread(target=stale_worker)
    thread.start()
    assert stale_ready.wait(timeout=5)
    clock.advance(seconds=ClaimLoopService.DISPATCH_LEASE_SECONDS + 1)
    winner = service_b.advance(
        session_id=SESSION,
        loop_id=loop_id,
        idempotency_key="generation-race-0001",
        expected_revision=selected["revision"],
    )
    resume_stale.set()
    thread.join(timeout=10)

    assert len(errors) == 1
    assert isinstance(errors[0], ClaimLoopServiceError)
    assert adapter.calls == 1
    assert winner["command_receipt"]["idempotency_key"] == (
        _advance_key(
            loop_id=loop_id,
            idempotency_key="generation-race-0001",
            expected_revision=selected["revision"],
            event_kind="result",
        )
    )
    events = service_b.store.events(session_id=SESSION, loop_id=loop_id)
    dispatches = [
        event
        for event in events
        if event.idempotency_key
        == _advance_key(
            loop_id=loop_id,
            idempotency_key="generation-race-0001",
            expected_revision=selected["revision"], event_kind="dispatch"
        )
    ]
    assert len(dispatches) == 1
    assert dispatches[0].command["dispatch_generation"] == 2


@pytest.mark.parametrize("concurrent_reader", [False, True])
def test_late_observed_tool_result_never_becomes_evidence(
    tmp_path: Path,
    concurrent_reader: bool,
) -> None:
    adapter = BlockingObservedAdapter()
    storage, service, created, clock = _fixture(tmp_path, adapter=adapter)
    service.DISPATCH_LEASE_SECONDS = 1
    loop_id = created["loop_id"]
    results: list[dict[str, Any]] = []
    errors: list[BaseException] = []

    def invoke() -> None:
        try:
            results.append(
                service.advance(
                    session_id=SESSION,
                    loop_id=loop_id,
                    idempotency_key="late-observation-0001",
                    expected_revision=created["revision"],
                )
            )
        except BaseException as exc:  # pragma: no cover - asserted below
            errors.append(exc)

    thread = threading.Thread(target=invoke)
    thread.start()
    assert adapter.entered.wait(timeout=5)
    clock.advance(seconds=2)
    if concurrent_reader:
        recovered = service.state_response(session_id=SESSION, loop_id=loop_id)
        assert recovered["active_dispatch_sha256"] is None
    adapter.release.set()
    thread.join(timeout=10)

    assert errors == []
    assert len(results) == 1
    assert results[0]["terminal_mode"] is None
    assert results[0]["phase"] == "awaiting_observation"
    assert adapter.calls == 1
    assert not any(
        event.event_type == "OBSERVATION_INGESTED"
        for event in service.store.events(session_id=SESSION, loop_id=loop_id)
    )
    with storage.connect() as connection:
        assert connection.execute(
            """SELECT COUNT(*) FROM claim_loop_tool_artifacts
            WHERE session_id=? AND loop_id=?""",
            (SESSION, loop_id),
        ).fetchone()[0] == 0


def test_durable_artifact_wins_expiry_and_unknown_blocks_late_artifact(
    tmp_path: Path,
) -> None:
    adapter = SwitchableEvidenceAdapter()
    adapter.configure_raise()
    _, service, created, clock = _fixture(tmp_path, adapter=adapter)
    loop_id = created["loop_id"]
    with pytest.raises(RuntimeError, match="tool-process crash"):
        service.advance(
            session_id=SESSION,
            loop_id=loop_id,
            idempotency_key="artifact-first-0001",
            expected_revision=created["revision"],
        )
    dispatch_state = service._raw_state(session_id=SESSION, loop_id=loop_id)
    adapter.configure_observed()
    synthetic = adapter.execute(
        action=dispatch_state.selected_action,
        state=dispatch_state,
        idempotency_key=dispatch_state.active_dispatch_sha256,
        timestamp=clock(),
    )
    artifact = _register_observed_artifact(
        service, dispatch_state, synthetic, timestamp=clock()
    )
    clock.advance(seconds=ClaimLoopService.DISPATCH_LEASE_SECONDS + 1)
    resolved = service.state_response(session_id=SESSION, loop_id=loop_id)
    assert resolved["active_dispatch_sha256"] is None
    assert any(
        event.event_type == "OBSERVATION_INGESTED"
        and event.command["artifact_receipt_sha256"] == artifact.receipt_sha256
        for event in service.store.events(session_id=SESSION, loop_id=loop_id)
    )

    other_adapter = SwitchableEvidenceAdapter()
    other_adapter.configure_raise()
    other_storage, other_service, other_created, other_clock = _fixture(
        tmp_path / "unknown-first", adapter=other_adapter
    )
    other_loop = other_created["loop_id"]
    with pytest.raises(RuntimeError, match="tool-process crash"):
        other_service.advance(
            session_id=SESSION,
            loop_id=other_loop,
            idempotency_key="unknown-first-0001",
            expected_revision=other_created["revision"],
        )
    stale_dispatch = other_service._raw_state(
        session_id=SESSION, loop_id=other_loop
    )
    dispatch_event = next(
        event
        for event in other_service.store.events(
            session_id=SESSION, loop_id=other_loop
        )
        if event.event_type == "ACTION_DISPATCH_STARTED"
    )
    other_clock.advance(seconds=ClaimLoopService.DISPATCH_LEASE_SECONDS + 1)
    other_service.state_response(session_id=SESSION, loop_id=other_loop)
    other_adapter.configure_observed()
    late = other_adapter.execute(
        action=stale_dispatch.selected_action,
        state=stale_dispatch,
        idempotency_key=stale_dispatch.active_dispatch_sha256,
        timestamp=dispatch_event.created_at,
    )
    with pytest.raises(ClaimLoopServiceError, match="active dispatch"):
        _register_observed_artifact(
            other_service,
            stale_dispatch,
            late,
            timestamp=dispatch_event.created_at,
        )
    with other_storage.connect() as connection:
        assert connection.execute(
            """SELECT COUNT(*) FROM claim_loop_tool_artifacts
            WHERE session_id=? AND loop_id=?""",
            (SESSION, other_loop),
        ).fetchone()[0] == 0


def test_observed_acquisition_recovers_after_preinterpretation_crash_without_redispatch(
    tmp_path: Path,
) -> None:
    adapter = SwitchableEvidenceAdapter()
    adapter.configure_raise()
    _, service, created, clock = _fixture(tmp_path, adapter=adapter)
    loop_id = created["loop_id"]
    with pytest.raises(RuntimeError, match="tool-process crash"):
        service.advance(
            session_id=SESSION,
            loop_id=loop_id,
            idempotency_key="acquisition-crash-observed-0001",
            expected_revision=created["revision"],
        )
    dispatch_state = service._raw_state(session_id=SESSION, loop_id=loop_id)
    adapter.configure_observed()
    result = adapter.execute(
        action=dispatch_state.selected_action,
        state=dispatch_state,
        idempotency_key=dispatch_state.active_dispatch_sha256,
        timestamp=clock(),
    )
    acquisition = service._register_acquisition_result(
        state=dispatch_state,
        adapter=adapter,
        result=result,
        timestamp=clock(),
    )
    assert service.store.tool_artifact_for_dispatch(
        session_id=SESSION,
        loop_id=loop_id,
        dispatch_sha256=dispatch_state.active_dispatch_sha256,
    ) is None

    recovery_adapter = SwitchableEvidenceAdapter()
    recovery = ClaimLoopService(
        service.storage,
        adapters={DEFAULT_EVIDENCE_TOOL_ID: recovery_adapter},
        artifact_interpreter=DeterministicMouldArtifactInterpreter(),
        cycle_pipeline=_cycle_pipeline(service.storage),
        cycle_transport_mode="deterministic_test_double",
        clock=clock,
    )
    recovered = recovery.state_response(session_id=SESSION, loop_id=loop_id)
    assert recovery_adapter.calls == 0
    assert recovered["active_dispatch_sha256"] is None
    artifact = recovery.store.tool_artifact_for_dispatch(
        session_id=SESSION,
        loop_id=loop_id,
        dispatch_sha256=acquisition.dispatch_sha256,
    )
    assert artifact is not None
    assert artifact.acquisition_receipt_sha256 == acquisition.receipt_sha256
    first_events = recovery.store.events(session_id=SESSION, loop_id=loop_id)
    assert sum(event.event_type == "OBSERVATION_INGESTED" for event in first_events) == 1
    assert recovery.state_response(session_id=SESSION, loop_id=loop_id) == recovered
    assert recovery_adapter.calls == 0
    assert recovery.store.events(session_id=SESSION, loop_id=loop_id) == first_events


def test_unavailable_acquisition_recovers_without_redispatch(
    tmp_path: Path,
) -> None:
    adapter = RaisingAdapter()
    _, service, created, clock = _fixture(tmp_path, adapter=adapter)
    loop_id = created["loop_id"]
    with pytest.raises(RuntimeError, match="tool-process crash"):
        service.advance(
            session_id=SESSION,
            loop_id=loop_id,
            idempotency_key="acquisition-crash-unavailable-0001",
            expected_revision=created["revision"],
        )
    dispatch_state = service._raw_state(session_id=SESSION, loop_id=loop_id)
    acquisition = _register_unavailable_acquisition(
        service, dispatch_state, adapter
    )
    recovery_adapter = RaisingAdapter()
    recovery = ClaimLoopService(
        service.storage,
        adapters={DEFAULT_EVIDENCE_TOOL_ID: recovery_adapter},
        artifact_interpreter=DeterministicMouldArtifactInterpreter(),
        cycle_pipeline=_cycle_pipeline(service.storage),
        cycle_transport_mode="deterministic_test_double",
        clock=clock,
    )
    recovered = recovery.state_response(session_id=SESSION, loop_id=loop_id)
    assert recovery_adapter.calls == 0
    assert recovered["active_dispatch_sha256"] is None
    events = recovery.store.events(session_id=SESSION, loop_id=loop_id)
    unavailable = [event for event in events if event.event_type == "TOOL_UNAVAILABLE"]
    assert len(unavailable) == 1
    assert unavailable[0].command["acquisition_receipt_sha256"] == (
        acquisition.receipt_sha256
    )
    assert recovery.state_response(session_id=SESSION, loop_id=loop_id) == recovered
    assert recovery_adapter.calls == 0
    assert recovery.store.events(session_id=SESSION, loop_id=loop_id) == events


def test_acquisition_registry_revalidates_models_and_raw_bytes(
    tmp_path: Path,
) -> None:
    adapter = SwitchableEvidenceAdapter()
    adapter.configure_raise()
    storage, service, created, clock = _fixture(
        tmp_path, adapter=adapter
    )
    loop_id = created["loop_id"]
    with pytest.raises(RuntimeError, match="tool-process crash"):
        service.advance(
            session_id=SESSION,
            loop_id=loop_id,
            idempotency_key="acquisition-integrity-0001",
            expected_revision=created["revision"],
        )
    state = service._raw_state(session_id=SESSION, loop_id=loop_id)
    adapter.configure_observed()
    result = adapter.execute(
        action=state.selected_action,
        state=state,
        idempotency_key=state.active_dispatch_sha256,
        timestamp=clock(),
    )
    receipt = service._register_acquisition_result(
        state=state,
        adapter=adapter,
        result=result,
        timestamp=clock(),
    )
    raw = receipt.sanitized_content.encode("utf-8")
    forged = receipt.model_copy(update={"receipt_sha256": "0" * 64})
    with pytest.raises(ValidationError):
        service.store.register_acquisition(forged, raw_payload=raw)
    with pytest.raises(ClaimLoopStoreError, match="raw payload"):
        service.store.register_acquisition(receipt, raw_payload=b"altered")
    with storage.connect() as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM claim_loop_acquisitions WHERE loop_id=?",
            (loop_id,),
        ).fetchone()[0] == 1
        connection.execute(
            "UPDATE claim_loop_acquisitions SET raw_payload=? WHERE receipt_sha256=?",
            (b"database-tamper", receipt.receipt_sha256),
        )
    with pytest.raises(ClaimLoopStoreError, match="database binding diverged"):
        service.store.acquisition(receipt.receipt_sha256)
    assert not any(
        event.event_type in {"OBSERVATION_INGESTED", "TOOL_UNAVAILABLE"}
        for event in service.store.events(session_id=SESSION, loop_id=loop_id)
    )


@pytest.mark.parametrize(
    "damage", ["raw_payload", "acquisition_json", "scalar_status", "delete"]
)
def test_journal_reads_rejoin_persisted_acquisition_authority(
    tmp_path: Path,
    damage: str,
) -> None:
    storage, service, created, _ = _fixture(
        tmp_path / damage, adapter=SyntheticMouldEvidenceAdapter()
    )
    loop_id = created["loop_id"]
    service.advance(
        session_id=SESSION,
        loop_id=loop_id,
        idempotency_key=f"acquisition-read-authority-{damage}-0001",
        expected_revision=created["revision"],
    )
    state = service.state(session_id=SESSION, loop_id=loop_id)
    artifact = service.store.tool_artifact(
        state.projection_ledger[0].artifact_receipt_sha256
    )
    assert artifact is not None
    with storage.connect() as connection:
        event_count = connection.execute(
            "SELECT COUNT(*) FROM claim_loop_events WHERE loop_id=?",
            (loop_id,),
        ).fetchone()[0]
        if damage == "raw_payload":
            connection.execute(
                """UPDATE claim_loop_acquisitions SET raw_payload=?
                WHERE receipt_sha256=?""",
                (b"tampered", artifact.acquisition_receipt_sha256),
            )
        elif damage == "acquisition_json":
            connection.execute(
                """UPDATE claim_loop_acquisitions SET acquisition_json=?
                WHERE receipt_sha256=?""",
                ("{}", artifact.acquisition_receipt_sha256),
            )
        elif damage == "scalar_status":
            connection.execute(
                """UPDATE claim_loop_acquisitions SET status='failed'
                WHERE receipt_sha256=?""",
                (artifact.acquisition_receipt_sha256,),
            )
        else:
            connection.execute(
                "DELETE FROM claim_loop_acquisitions WHERE receipt_sha256=?",
                (artifact.acquisition_receipt_sha256,),
            )

    state_response = service.state_response(session_id=SESSION, loop_id=loop_id)
    audit = service.audit(session_id=SESSION, loop_id=loop_id)
    assert state_response["state_sha256"] == state.state_sha256
    assert audit["state_sha256"] == state.state_sha256
    assert service.store.acquisition(
        artifact.acquisition_receipt_sha256
    ) == artifact.acquisition_receipt
    with storage.connect() as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM claim_loop_events WHERE loop_id=?",
            (loop_id,),
        ).fetchone()[0] == event_count


def test_terminal_packet_rejoins_every_acquisition_authority(
    tmp_path: Path,
) -> None:
    storage, service, created, _ = _fixture(
        tmp_path, adapter=SyntheticMouldEvidenceAdapter()
    )
    response = created
    for index in range(30):
        if response["phase"] == "decision_ready":
            break
        response = service.advance(
            session_id=SESSION,
            loop_id=created["loop_id"],
            idempotency_key=f"packet-acquisition-{index:04d}",
            expected_revision=response["revision"],
        )
    assert response["phase"] == "decision_ready"
    assert service.packet(
        session_id=SESSION, loop_id=created["loop_id"]
    )["source_state_sha256"] == response["state_sha256"]
    state = service.state(session_id=SESSION, loop_id=created["loop_id"])
    artifact = service.store.tool_artifact(
        state.projection_ledger[0].artifact_receipt_sha256
    )
    assert artifact is not None
    with storage.connect() as connection:
        connection.execute(
            "DELETE FROM claim_loop_acquisitions WHERE receipt_sha256=?",
            (artifact.acquisition_receipt_sha256,),
        )
    repaired_packet = service.packet(session_id=SESSION, loop_id=created["loop_id"])
    assert repaired_packet["source_state_sha256"] == response["state_sha256"]
    assert service.store.acquisition(
        artifact.acquisition_receipt_sha256
    ) == artifact.acquisition_receipt


def test_replay_cache_never_exposes_mutable_authority(
    tmp_path: Path,
) -> None:
    _, service, created, _ = _fixture(tmp_path)
    loop_id = created["loop_id"]
    canonical = service.state(session_id=SESSION, loop_id=loop_id)
    canonical_process = json.loads(json.dumps(canonical.process))
    canonical_checklist = json.loads(json.dumps(canonical.checklist))
    canonical_facts = tuple(json.loads(json.dumps(canonical.facts)))
    canonical_accepted = json.loads(json.dumps(canonical.accepted_artifacts))

    canonical.process["current_overlay"]["next_action_node_id"] = "node.forged"
    canonical.checklist["items"][0]["status"] = "forged"
    canonical.facts[0]["value"] = "forged"
    canonical.accepted_artifacts["process"]["forged"] = True

    replayed = service.state(session_id=SESSION, loop_id=loop_id)
    assert replayed is not canonical
    assert replayed.process == canonical_process
    assert replayed.checklist == canonical_checklist
    assert replayed.facts == canonical_facts
    assert replayed.accepted_artifacts == canonical_accepted
    replayed_payload = replayed.model_dump(mode="json", exclude={"state_sha256"})
    if not replayed.native_proposal_revisions:
        replayed_payload.pop("native_proposal_revisions")
    assert replayed.state_sha256 == digest_value(replayed_payload)

    selected = service.select_action(
        session_id=SESSION,
        loop_id=loop_id,
        idempotency_key="cache-mutation-select-0001",
        expected_revision=replayed.revision,
    )
    assert selected["state_sha256"] != canonical.state_sha256
    assert service.state(session_id=SESSION, loop_id=loop_id).process == canonical_process


@pytest.mark.parametrize(
    "damage",
    [
        "receipt_hash",
        "content_hash",
        "span",
        "value",
        "page",
        "version",
        "action",
        "capability",
        "dispatch",
        "interpretation",
    ],
)
def test_store_rejects_forged_tool_artifact_authority(
    tmp_path: Path,
    damage: str,
) -> None:
    adapter = SwitchableEvidenceAdapter()
    adapter.configure_raise()
    _, service, created, clock = _fixture(
        tmp_path / damage, adapter=adapter
    )
    loop_id = created["loop_id"]
    with pytest.raises(RuntimeError, match="tool-process crash"):
        service.advance(
            session_id=SESSION,
            loop_id=loop_id,
            idempotency_key=f"forged-artifact-{damage}-0001",
            expected_revision=created["revision"],
        )
    state = service._raw_state(session_id=SESSION, loop_id=loop_id)
    adapter.configure_observed()
    result = adapter.execute(
        action=state.selected_action,
        state=state,
        idempotency_key=state.active_dispatch_sha256,
        timestamp=clock(),
    )
    payload = _server_interpreted_tool_payload(
        service=service,
        state=state,
        result=result,
        timestamp=clock(),
    )
    if damage == "content_hash":
        payload["sanitized_content"] += " altered"
    elif damage == "span":
        source = payload["observation"]["source_refs"][0]
        source["text_start"] = 1
        source["sanitized_excerpt"] = payload["sanitized_content"][1:]
        source["span_sha256"] = digest_text(source["sanitized_excerpt"])
    elif damage == "value":
        payload["observation"]["value"] = "unsupported value"
    elif damage == "page":
        payload["observation"]["source_refs"][0]["page"] = 2
    elif damage == "version":
        payload["artifact_source_version"] = "stale-record-version"
        payload["observation"]["source_refs"][0]["source_version"] = (
            "stale-record-version"
        )
    elif damage == "action":
        payload["action_sha256"] = "f" * 64
        payload["action_id"] = f"action.{payload['action_sha256']}"
    elif damage == "capability":
        payload["adapter_id"] = "casepath.wrong-capability/1.0.0"
        payload["observation"]["source_refs"][0]["adapter_id"] = payload[
            "adapter_id"
        ]
    elif damage == "dispatch":
        payload["dispatch_sha256"] = "f" * 64
    elif damage == "interpretation":
        payload["interpretation"]["selected_assertion_id"] = (
            "mould.forged-assertion/1"
        )
    try:
        receipt = _tool_artifact_from_payload(payload)
    except ValidationError:
        with service.store.connect() as connection:
            assert connection.execute(
                """SELECT COUNT(*) FROM claim_loop_tool_artifacts
                WHERE session_id=? AND loop_id=?""",
                (SESSION, loop_id),
            ).fetchone()[0] == 0
        return
    if damage == "receipt_hash":
        receipt = receipt.model_copy(update={"receipt_sha256": "0" * 64})
    event_count = len(
        service.store.events(session_id=SESSION, loop_id=loop_id)
    )
    with pytest.raises((ClaimLoopStoreError, ValidationError)):
        service.store.register_tool_artifact(receipt)
    assert len(
        service.store.events(session_id=SESSION, loop_id=loop_id)
    ) == event_count
    with service.store.connect() as connection:
        assert connection.execute(
            """SELECT COUNT(*) FROM claim_loop_tool_artifacts
            WHERE session_id=? AND loop_id=?""",
            (SESSION, loop_id),
        ).fetchone()[0] == 0


@pytest.mark.parametrize(
    "damage",
    ["unknown_receipt", "observation", "action", "dispatch", "result_key"],
)
def test_store_append_rejects_forged_observation_events(
    tmp_path: Path,
    damage: str,
) -> None:
    request_key = f"direct-observation-{damage}-0001"
    adapter = SwitchableEvidenceAdapter()
    adapter.configure_raise()
    _, service, created, clock = _fixture(
        tmp_path / damage, adapter=adapter
    )
    loop_id = created["loop_id"]
    with pytest.raises(RuntimeError, match="tool-process crash"):
        service.advance(
            session_id=SESSION,
            loop_id=loop_id,
            idempotency_key=request_key,
            expected_revision=created["revision"],
        )
    state = service._raw_state(session_id=SESSION, loop_id=loop_id)
    adapter.configure_observed()
    result = adapter.execute(
        action=state.selected_action,
        state=state,
        idempotency_key=state.active_dispatch_sha256,
        timestamp=clock(),
    )
    artifact = _register_observed_artifact(
        service, state, result, timestamp=clock()
    )
    request_sha256 = digest_value(
        {
            "expected_revision": created["revision"],
            "requested_adapter_id": None,
        }
    )
    command = service._observation_command(
        state=state,
        artifact=artifact,
        advance_request_sha256=request_sha256,
    )
    result_key = claim_loop_internal_event_key_v1(
        session_id=SESSION,
        loop_id=loop_id,
        client_idempotency_key=request_key,
        request_type="advance",
        request_sha256=request_sha256,
        event_kind="result",
    )
    if damage == "unknown_receipt":
        command["artifact_receipt_sha256"] = "0" * 64
    elif damage == "observation":
        command["observation"]["value"] = "forged value"
    elif damage == "action":
        command["action_id"] = "action.forged"
    elif damage == "dispatch":
        command["dispatch_sha256"] = "f" * 64
    else:
        result_key = "@casepath-claim-loop." + ("0" * 64)
    event_count = len(
        service.store.events(session_id=SESSION, loop_id=loop_id)
    )
    with pytest.raises(ClaimLoopStoreError):
        service.store.append(
            session_id=SESSION,
            loop_id=loop_id,
            event_type="OBSERVATION_INGESTED",
            idempotency_key=result_key,
            command=command,
            timestamp=artifact.registered_at,
            expected_revision=state.revision,
        )
    assert len(
        service.store.events(session_id=SESSION, loop_id=loop_id)
    ) == event_count


@pytest.mark.parametrize("legacy", [False, True])
def test_concurrent_store_initialization_is_serialized(
    tmp_path: Path,
    legacy: bool,
) -> None:
    database = tmp_path / ("legacy.db" if legacy else "fresh.db")
    if legacy:
        with sqlite3.connect(database) as connection:
            connection.execute(
                """CREATE TABLE claim_loop_client_requests (
                    session_id TEXT NOT NULL,
                    loop_id TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    request_type TEXT NOT NULL,
                    request_sha256 TEXT NOT NULL,
                    request_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY(session_id,loop_id,idempotency_key)
                )"""
            )
    errors: list[BaseException] = []
    barrier = threading.Barrier(4)

    def initialize() -> None:
        try:
            barrier.wait(timeout=5)
            ClaimLoopStore(database)
        except BaseException as exc:  # pragma: no cover - asserted below
            errors.append(exc)

    threads = [threading.Thread(target=initialize) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert errors == []
    with sqlite3.connect(database) as connection:
        columns = {
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(claim_loop_client_requests)"
            )
        }
    assert {
        "status",
        "result_event_sha256",
        "response_sha256",
        "dispatch_started_at",
        "dispatch_expires_at",
        "dispatch_generation",
    } <= columns


def test_deterministic_cycle_receipt_rejects_nonzero_cost(tmp_path: Path) -> None:
    _, service, created, _ = _fixture(tmp_path)
    state = service.state(session_id=SESSION, loop_id=created["loop_id"])
    payload = state.six_agent_cycle_receipt.model_dump(
        mode="json", exclude={"receipt_sha256"}
    )
    payload["cost_usd"] = 0.01

    with pytest.raises(ValidationError, match="zero-provider cycle activity"):
        SixAgentCycleReceipt.model_validate(
            {**payload, "receipt_sha256": digest_value(payload)}
        )


def _prospective_route_observation() -> dict[str, Any]:
    return {
        "contract": "casepath.openrouter-observed-route/1.0.0",
        "actual_endpoint_tag": "deepinfra/fp4",
        "upstream_provider": "DeepInfra",
        "response_model": "nvidia/nemotron-3-ultra-550b-a55b-20260604",
        "endpoint_active": True,
        "runtime_activated": False,
        "provider_policy": {
            "only": ["deepinfra/fp4"],
            "allow_fallbacks": False,
            "require_parameters": True,
            "data_collection": "deny",
        },
        "automatic_retry": False,
    }


def test_prospective_route_requires_observed_exact_endpoint_identity() -> None:
    observed = _prospective_route_observation()
    validated = langchain_runtime.validate_prospective_route_identity(
        route_observation=observed
    )

    assert validated["actual_endpoint_tag"] == "deepinfra/fp4"
    assert validated["upstream_provider"] == "DeepInfra"
    assert validated["response_model"].endswith("-20260604")
    assert validated["endpoint_active"] is True
    assert validated["identity_valid"] is True
    assert validated["runtime_activated"] is False
    assert langchain_runtime.OPENROUTER_ENDPOINT_TAG == "together"
    assert (
        langchain_runtime.prospective_deepinfra_route_contract()["activated"]
        is False
    )


@pytest.mark.parametrize(
    "damage",
    (
        "missing_provider",
        "wrong_provider",
        "provider_case",
        "missing_model",
        "undated_model",
        "wrong_model_revision",
        "missing_endpoint",
        "generic_endpoint",
        "wrong_endpoint",
        "inactive_endpoint",
        "runtime_already_activated",
        "missing_only",
        "wrong_only",
        "missing_fallback",
        "fallback_enabled",
        "missing_required_parameters",
        "required_parameters_disabled",
        "missing_data_policy",
        "data_policy_allowed",
        "missing_retry_policy",
        "retry_enabled",
    ),
)
def test_prospective_route_rejects_incomplete_or_inexact_identity(
    damage: str,
) -> None:
    observed = _prospective_route_observation()
    if damage == "missing_provider":
        observed.pop("upstream_provider")
    elif damage == "wrong_provider":
        observed["upstream_provider"] = "Together"
    elif damage == "provider_case":
        observed["upstream_provider"] = "deepinfra"
    elif damage == "missing_model":
        observed.pop("response_model")
    elif damage == "undated_model":
        observed["response_model"] = langchain_runtime.NEMOTRON_MODEL
    elif damage == "wrong_model_revision":
        observed["response_model"] = (
            f"{langchain_runtime.NEMOTRON_MODEL}-20260603"
        )
    elif damage == "missing_endpoint":
        observed.pop("actual_endpoint_tag")
    elif damage == "generic_endpoint":
        observed["actual_endpoint_tag"] = "deepinfra"
    elif damage == "wrong_endpoint":
        observed["actual_endpoint_tag"] = "deepinfra/fp8"
    elif damage == "inactive_endpoint":
        observed["endpoint_active"] = False
    elif damage == "runtime_already_activated":
        observed["runtime_activated"] = True
    elif damage == "missing_only":
        observed["provider_policy"].pop("only")
    elif damage == "wrong_only":
        observed["provider_policy"]["only"] = ["deepinfra"]
    elif damage == "missing_fallback":
        observed["provider_policy"].pop("allow_fallbacks")
    elif damage == "fallback_enabled":
        observed["provider_policy"]["allow_fallbacks"] = True
    elif damage == "missing_required_parameters":
        observed["provider_policy"].pop("require_parameters")
    elif damage == "required_parameters_disabled":
        observed["provider_policy"]["require_parameters"] = False
    elif damage == "missing_data_policy":
        observed["provider_policy"].pop("data_collection")
    elif damage == "data_policy_allowed":
        observed["provider_policy"]["data_collection"] = "allow"
    elif damage == "missing_retry_policy":
        observed.pop("automatic_retry")
    else:
        observed["automatic_retry"] = True

    with pytest.raises(langchain_runtime.OpenRouterProtocolError):
        langchain_runtime.validate_prospective_route_identity(
            route_observation=observed
        )


def test_server_owned_correction_materially_changes_only_target(
    tmp_path: Path,
) -> None:
    adapter = SyntheticMouldEvidenceAdapter()
    storage, service, created, _ = _fixture(tmp_path, adapter=adapter)
    loop_id = created["loop_id"]
    clarified = service.advance(
        session_id=SESSION,
        loop_id=loop_id,
        idempotency_key="correction-source-advance-0001",
        expected_revision=created["revision"],
    )
    observed = service.advance(
        session_id=SESSION,
        loop_id=loop_id,
        idempotency_key="correction-source-advance-0002",
        expected_revision=clarified["revision"],
    )
    before = service.state(session_id=SESSION, loop_id=loop_id)
    source_entry = before.projection_ledger[-1]
    source_artifact = service.store.tool_artifact(
        source_entry.artifact_receipt_sha256
    )
    assert source_artifact is not None
    source = source_artifact.observation.source_refs[0]
    before_fact = next(
        value for value in before.facts if value["fact_id"] == "fact_cause"
    )
    before_path = tuple(before.process["selected_path"])
    unrelated_before = digest_value(
        [value for value in before.facts if value["fact_id"] != "fact_cause"]
    )
    event_count = len(service.store.events(session_id=SESSION, loop_id=loop_id))

    correction = _admit_correction(
        service,
        session_id=SESSION,
        loop_id=loop_id,
        source_artifact_receipt_sha256=source_artifact.receipt_sha256,
        effect=CorrectionEffect(
            fact_id="fact_cause",
            evidence_item_id="technical_assessment",
            value=source.sanitized_excerpt,
            fact_state="conflicting",
            normalized_value=None,
            explanation=(
                "The prior positive interpretation is retracted because the "
                "admitted source now has an unresolved internal conflict."
            ),
            evidence_status="provided_sufficient",
        ),
        suffix="material-local",
    )
    assert len(service.store.events(session_id=SESSION, loop_id=loop_id)) == event_count
    authority = service.store.correction_artifact(
        correction.correction_artifact_receipt_sha256
    )
    assert authority is not None
    assert authority.before_fact_sha256 == digest_value(before_fact)

    response = service.apply_correction(
        session_id=SESSION,
        loop_id=loop_id,
        correction_id=correction.correction_id,
        idempotency_key="apply-material-correction-0001",
    )
    after = service.state(session_id=SESSION, loop_id=loop_id)
    after_fact = next(
        value for value in after.facts if value["fact_id"] == "fact_cause"
    )

    assert response["revision"] == observed["revision"] + 1
    assert after_fact["state"] == "conflicting"
    assert after_fact["normalized_value"] == "unresolved"
    assert after_fact["decision_value"] == "cause_unresolved"
    assert tuple(after.process["selected_path"]) != before_path
    assert digest_value(
        [value for value in after.facts if value["fact_id"] != "fact_cause"]
    ) == unrelated_before
    assert authority.expected_after_fact_sha256 == digest_value(after_fact)
    assert authority.unrelated_facts_before_sha256 == unrelated_before
    assert authority.unrelated_facts_after_sha256 == unrelated_before
    assert authority.rollback_fact_sha256 == authority.before_fact_sha256
    assert after.six_agent_cycle_receipt.cycle_kind == "correction"
    assert after.six_agent_cycle_receipt.prior_state_sha256 == before.state_sha256
    assert after.six_agent_cycle_receipt.trigger_sha256 == correction.correction_sha256
    assert len(after.six_agent_cycle_receipt.agent_ids) == 6
    assert len(after.six_agent_cycle_receipt.deterministic_gate_ids) == 3
    assert after.six_agent_cycle_receipt.transport_mode == (
        "deterministic_test_double"
    )
    assert after.six_agent_cycle_receipt.model_calls == 0
    assert after.six_agent_cycle_receipt.provider_calls == 0
    assert after.six_agent_cycle_receipt.credential_access_status == (
        "none_due_to_zero_provider_calls"
    )
    assert after.six_agent_cycle_receipt.credential_access_receipt_sha256s == ()
    assert after.six_agent_cycle_receipt.cost_status == "exact"
    assert after.six_agent_cycle_receipt.cost_usd == 0.0
    assert len(after.six_agent_graph_audit["agents"]) == 6
    assert {
        value["actor_type"]
        for value in after.six_agent_graph_audit["agents"]
    } == {"deterministic_structured_agent"}
    assert all(
        value["model"] is None
        and value["provider"] is None
        and value["call_count"] == 0
        for value in after.six_agent_graph_audit["agents"]
    )
    assert len(after.six_agent_graph_audit["deterministic_gates"]) == 3
    assert after.six_agent_graph_audit["model_assisted"] is False
    with storage.connect() as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM model_calls"
        ).fetchone()[0] == 0


@pytest.mark.parametrize(
    "forgery",
    (
        "artifact_hash",
        "artifact_schema",
        "correction_hash",
        "correction_schema",
    ),
)
def test_store_revalidates_correction_instances_before_writing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    forgery: str,
) -> None:
    adapter = SyntheticMouldEvidenceAdapter()
    storage, service, created, _ = _fixture(tmp_path, adapter=adapter)
    loop_id = created["loop_id"]
    service.advance(
        session_id=SESSION,
        loop_id=loop_id,
        idempotency_key=f"correction-revalidation-source-{forgery}",
        expected_revision=created["revision"],
    )
    state = service.state(session_id=SESSION, loop_id=loop_id)
    artifact = service.store.tool_artifact(
        state.projection_ledger[0].artifact_receipt_sha256
    )
    assert artifact is not None
    source = artifact.observation.source_refs[0]
    adapter_id = f"casepath.test-correction-revalidation.{forgery}"
    correction_adapter = StaticCorrectionAdapter(
        CorrectionEffect(
            fact_id=artifact.observation.fact_id,
            evidence_item_id=artifact.observation.evidence_item_id,
            value=source.sanitized_excerpt,
            fact_state="conflicting",
            normalized_value=None,
            explanation="Retract the prior interpretation under exact authority.",
            evidence_status="provided_sufficient",
        ),
        adapter_id=adapter_id,
    )
    service.correction_adapters[adapter_id] = correction_adapter
    service.store.correction_adapters[adapter_id] = correction_adapter
    captured: dict[str, Any] = {}
    original_register = service.store.register_correction

    def capture_correction(**kwargs: Any) -> None:
        captured.update(kwargs)

    monkeypatch.setattr(service.store, "register_correction", capture_correction)
    service.register_correction(
        session_id=SESSION,
        loop_id=loop_id,
        source_artifact_receipt_sha256=artifact.receipt_sha256,
        correction_adapter_id=adapter_id,
    )
    monkeypatch.setattr(service.store, "register_correction", original_register)
    correction_artifact = captured["correction_artifact"]
    correction = captured["correction"]

    if forgery == "artifact_hash":
        correction_artifact = correction_artifact.model_copy(
            update={"receipt_sha256": "0" * 64}
        )
    elif forgery == "artifact_schema":
        correction_artifact = correction_artifact.model_copy(
            update={"contract": "casepath.forged-correction-artifact/1.0.0"}
        )
    elif forgery == "correction_hash":
        correction = correction.model_copy(
            update={"correction_sha256": "0" * 64}
        )
    else:
        correction = correction.model_copy(
            update={"contract": "casepath.forged-scoped-correction/1.0.0"}
        )

    with pytest.raises(ValidationError):
        service.store.register_correction(
            correction_artifact=correction_artifact,
            correction=correction,
            source_session_id=SESSION,
            source_loop_id=loop_id,
            timestamp=captured["timestamp"],
        )
    with storage.connect() as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM claim_loop_correction_artifacts"
        ).fetchone()[0] == 0
        assert connection.execute(
            "SELECT COUNT(*) FROM claim_loop_corrections"
        ).fetchone()[0] == 0


def test_safe_correction_reuse_requires_matching_same_session_state(
    tmp_path: Path,
) -> None:
    adapter = SyntheticMouldEvidenceAdapter()
    _, service, source_created, _ = _fixture(tmp_path, adapter=adapter)
    source_loop = source_created["loop_id"]
    source_clarified = service.advance(
        session_id=SESSION,
        loop_id=source_loop,
        idempotency_key="reuse-source-observation-0001",
        expected_revision=source_created["revision"],
    )
    service.advance(
        session_id=SESSION,
        loop_id=source_loop,
        idempotency_key="reuse-source-observation-0002",
        expected_revision=source_clarified["revision"],
    )
    source_before = service.state(session_id=SESSION, loop_id=source_loop)
    source_artifact = service.store.tool_artifact(
        source_before.projection_ledger[-1].artifact_receipt_sha256
    )
    assert source_artifact is not None
    source_ref = source_artifact.observation.source_refs[0]
    correction = _admit_correction(
        service,
        session_id=SESSION,
        loop_id=source_loop,
        source_artifact_receipt_sha256=source_artifact.receipt_sha256,
        effect=CorrectionEffect(
            fact_id="fact_cause",
            evidence_item_id="technical_assessment",
            value=source_ref.sanitized_excerpt,
            fact_state="conflicting",
            normalized_value=None,
            explanation="The accepted interpretation is conservatively retracted.",
            evidence_status="provided_sufficient",
        ),
        suffix="reuse-source",
    )

    target_created = service.create(
        session_id=SESSION,
        source_run_id=source_before.source_run_id,
        idempotency_key="create-matching-reuse-loop-0002",
    )
    target_loop = target_created["loop_id"]
    target_clarified = service.advance(
        session_id=SESSION,
        loop_id=target_loop,
        idempotency_key="reuse-target-observation-0001",
        expected_revision=target_created["revision"],
    )
    service.advance(
        session_id=SESSION,
        loop_id=target_loop,
        idempotency_key="reuse-target-observation-0002",
        expected_revision=target_clarified["revision"],
    )
    target_before = service.state(session_id=SESSION, loop_id=target_loop)
    target_unrelated_before = digest_value(
        [
            value
            for value in target_before.facts
            if value["fact_id"] != "fact_cause"
        ]
    )
    target_tail_before_unapplied = service.store.events(
        session_id=SESSION, loop_id=target_loop
    )
    with pytest.raises(ClaimLoopServiceError, match="not durably applied"):
        service.reuse_correction(
            session_id=SESSION,
            loop_id=target_loop,
            correction_id=correction.correction_id,
            idempotency_key="reuse-before-source-apply-0001",
        )
    assert service.store.events(
        session_id=SESSION, loop_id=target_loop
    ) == target_tail_before_unapplied
    source_applied = service.apply_correction(
        session_id=SESSION,
        loop_id=source_loop,
        correction_id=correction.correction_id,
        idempotency_key="reuse-source-apply-0001",
    )
    source_after_sha256 = source_applied["state_sha256"]
    abandoned_reuse_key = "abandoned-reuse-target-0002"
    abandoned_reuse_request = {"correction_id": correction.correction_id}
    service._bind_client_request(
        session_id=SESSION,
        loop_id=target_loop,
        idempotency_key=abandoned_reuse_key,
        request_type="reuse_correction",
        request=abandoned_reuse_request,
    )

    reused = service.reuse_correction(
        session_id=SESSION,
        loop_id=target_loop,
        correction_id=correction.correction_id,
        idempotency_key="reuse-target-apply-0001",
    )
    _assert_stable_superseded_request(
        service=service,
        loop_id=target_loop,
        idempotency_key=abandoned_reuse_key,
        request_type="reuse_correction",
        request=abandoned_reuse_request,
        retry=lambda: service.reuse_correction(
            session_id=SESSION,
            loop_id=target_loop,
            correction_id=correction.correction_id,
            idempotency_key=abandoned_reuse_key,
        ),
    )
    target_after = service.state(session_id=SESSION, loop_id=target_loop)
    target_fact = next(
        value for value in target_after.facts if value["fact_id"] == "fact_cause"
    )
    receipt = target_after.correction_reuse_receipts[-1]

    assert target_fact["state"] == "conflicting"
    assert target_fact["normalized_value"] == "unresolved"
    assert receipt.target_parent_state_sha256 == target_before.state_sha256
    assert receipt.target_expected_after_fact_sha256 == digest_value(target_fact)
    assert receipt.target_unrelated_facts_before_sha256 == (
        target_unrelated_before
    )
    assert receipt.target_unrelated_facts_after_sha256 == (
        target_unrelated_before
    )
    assert service.state(
        session_id=SESSION, loop_id=source_loop
    ).state_sha256 == source_after_sha256
    replay = service.reuse_correction(
        session_id=SESSION,
        loop_id=target_loop,
        correction_id=correction.correction_id,
        idempotency_key="reuse-target-apply-0001",
    )
    assert _bytes(replay) == _bytes(reused)
    assert sum(
        event.event_type == "CORRECTION_REUSED"
        for event in service.store.events(session_id=SESSION, loop_id=target_loop)
    ) == 1

    unmatched = service.create(
        session_id=SESSION,
        source_run_id=source_before.source_run_id,
        idempotency_key="create-unmatched-reuse-loop-0003",
    )
    unmatched_tail = service.store.events(
        session_id=SESSION, loop_id=unmatched["loop_id"]
    )
    with pytest.raises(ClaimLoopServiceError, match="matching source span"):
        service.reuse_correction(
            session_id=SESSION,
            loop_id=unmatched["loop_id"],
            correction_id=correction.correction_id,
            idempotency_key="reuse-unmatched-0001",
        )
    assert service.store.events(
        session_id=SESSION, loop_id=unmatched["loop_id"]
    ) == unmatched_tail


def test_correction_admission_rejects_unsupported_stale_and_noop_proposals(
    tmp_path: Path,
) -> None:
    adapter = SyntheticMouldEvidenceAdapter()
    storage, service, created, _ = _fixture(tmp_path, adapter=adapter)
    loop_id = created["loop_id"]
    clarified = service.advance(
        session_id=SESSION,
        loop_id=loop_id,
        idempotency_key="correction-negative-source-0001",
        expected_revision=created["revision"],
    )
    service.advance(
        session_id=SESSION,
        loop_id=loop_id,
        idempotency_key="correction-negative-source-0002",
        expected_revision=clarified["revision"],
    )
    state = service.state(session_id=SESSION, loop_id=loop_id)
    artifact = service.store.tool_artifact(
        state.projection_ledger[-1].artifact_receipt_sha256
    )
    assert artifact is not None
    observation = artifact.observation
    source = observation.source_refs[0]
    tail = service.store.events(session_id=SESSION, loop_id=loop_id)

    invalid = (
        (
            CorrectionEffect(
                fact_id=observation.fact_id,
                evidence_item_id=observation.evidence_item_id,
                value=source.sanitized_excerpt,
                fact_state="known",
                normalized_value="not_a_bounded_route",
                explanation="Authority asserts a route outside the frozen catalog.",
                evidence_status="provided_sufficient",
            ),
            None,
            "bounded fact catalog",
        ),
        (
            CorrectionEffect(
                fact_id="fact_damage_scope",
                evidence_item_id=observation.evidence_item_id,
                value="Mismatched correction target.",
                fact_state="conflicting",
                normalized_value=None,
                explanation="Unsupported raw value.",
                evidence_status="provided_sufficient",
            ),
            None,
            "exact source span",
        ),
        (
            CorrectionEffect(
                fact_id=observation.fact_id,
                evidence_item_id=observation.evidence_item_id,
                value=source.sanitized_excerpt,
                fact_state="conflicting",
                normalized_value="tenant_use",
                explanation="Non-known state cannot mint a route value.",
                evidence_status="provided_sufficient",
            ),
            None,
            "exact source span",
        ),
        (
            CorrectionEffect(
                fact_id=observation.fact_id,
                evidence_item_id=observation.evidence_item_id,
                value=source.sanitized_excerpt,
                fact_state=observation.fact_state,
                normalized_value=observation.normalized_value,
                explanation=observation.explanation,
                evidence_status=observation.evidence_status,
            ),
            None,
            "no-op",
        ),
        (
            CorrectionEffect(
                fact_id=observation.fact_id,
                evidence_item_id=observation.evidence_item_id,
                value=source.sanitized_excerpt,
                fact_state="conflicting",
                normalized_value=None,
                explanation="Expired conservative correction.",
                evidence_status="provided_sufficient",
            ),
            "2020-01-01T00:00:00+00:00",
            "expired",
        ),
    )
    for index, (effect, expires_at, message) in enumerate(invalid):
        with pytest.raises(ClaimLoopServiceError, match=message):
            _admit_correction(
                service,
                session_id=SESSION,
                loop_id=loop_id,
                source_artifact_receipt_sha256=artifact.receipt_sha256,
                effect=effect,
                expires_at=expires_at,
                suffix=f"negative-{index}",
            )
        assert service.store.events(session_id=SESSION, loop_id=loop_id) == tail
        with storage.connect() as connection:
            assert connection.execute(
                "SELECT COUNT(*) FROM claim_loop_corrections"
            ).fetchone()[0] == 0
            assert connection.execute(
                "SELECT COUNT(*) FROM claim_loop_correction_artifacts"
            ).fetchone()[0] == 0


def test_stale_local_correction_fails_before_cycle_or_event(tmp_path: Path) -> None:
    adapter = SyntheticMouldEvidenceAdapter()
    _, service, created, _ = _fixture(tmp_path, adapter=adapter)
    loop_id = created["loop_id"]
    first = service.advance(
        session_id=SESSION,
        loop_id=loop_id,
        idempotency_key="stale-correction-first-0001",
        expected_revision=created["revision"],
    )
    parent = service.state(session_id=SESSION, loop_id=loop_id)
    artifact = service.store.tool_artifact(
        parent.projection_ledger[0].artifact_receipt_sha256
    )
    assert artifact is not None
    source = artifact.observation.source_refs[0]
    correction = _admit_correction(
        service,
        session_id=SESSION,
        loop_id=loop_id,
        source_artifact_receipt_sha256=artifact.receipt_sha256,
        effect=CorrectionEffect(
            fact_id=artifact.observation.fact_id,
            evidence_item_id=artifact.observation.evidence_item_id,
            value=source.sanitized_excerpt,
            fact_state="conflicting",
            normalized_value=None,
            explanation="Stale-parent fixture.",
            evidence_status="provided_sufficient",
        ),
        suffix="stale-parent",
    )
    service.advance(
        session_id=SESSION,
        loop_id=loop_id,
        idempotency_key="stale-correction-second-0002",
        expected_revision=first["revision"],
    )
    tail = service.store.events(session_id=SESSION, loop_id=loop_id)
    with pytest.raises(ClaimLoopServiceError, match="parent identity is stale"):
        service.apply_correction(
            session_id=SESSION,
            loop_id=loop_id,
            correction_id=correction.correction_id,
            idempotency_key="apply-stale-correction-0001",
        )
    assert service.store.events(session_id=SESSION, loop_id=loop_id) == tail


def test_session_reset_removes_every_claim_loop_table(tmp_path: Path) -> None:
    storage, service, created, _ = _fixture(
        tmp_path, adapter=SyntheticMouldEvidenceAdapter()
    )
    service.advance(
        session_id=SESSION,
        loop_id=created["loop_id"],
        idempotency_key="advance-before-reset-0001",
        expected_revision=created["revision"],
    )
    before = service.state(session_id=SESSION, loop_id=created["loop_id"])
    artifact = service.store.tool_artifact(
        before.projection_ledger[0].artifact_receipt_sha256
    )
    assert artifact is not None
    source = artifact.observation.source_refs[0]
    _admit_correction(
        service,
        session_id=SESSION,
        loop_id=created["loop_id"],
        source_artifact_receipt_sha256=artifact.receipt_sha256,
        effect=CorrectionEffect(
            fact_id=artifact.observation.fact_id,
            evidence_item_id=artifact.observation.evidence_item_id,
            value=source.sanitized_excerpt,
            fact_state="conflicting",
            normalized_value=None,
            explanation="Reset fixture retracts the prior interpretation.",
            evidence_status="provided_sufficient",
        ),
        suffix="reset",
    )

    counts = storage.reset(session_id=SESSION)

    assert counts["claim_loop_events"] > 0
    assert counts["claim_loop_checkpoints"] > 0
    assert counts["claim_loop_client_requests"] > 0
    assert counts["claim_loop_corrections"] > 0
    assert counts["claim_loop_correction_artifacts"] > 0
    assert counts["claim_loop_acquisitions"] > 0
    assert counts["claim_loop_tool_artifacts"] > 0
    with storage.connect() as connection:
        for table, column in (
            ("claim_loop_events", "session_id"),
            ("claim_loop_checkpoints", "session_id"),
            ("claim_loop_corrections", "source_session_id"),
            ("claim_loop_correction_artifacts", "session_id"),
            ("claim_loop_acquisitions", "session_id"),
            ("claim_loop_tool_artifacts", "session_id"),
            ("claim_loop_client_requests", "session_id"),
        ):
            assert connection.execute(
                f"SELECT COUNT(*) FROM {table} WHERE {column}=?",  # noqa: S608
                (SESSION,),
            ).fetchone()[0] == 0


def test_full_generated_mould_loop_reaches_decision_ready_packet(
    tmp_path: Path,
) -> None:
    storage, service, created, _ = _fixture(
        tmp_path, adapter=SyntheticMouldEvidenceAdapter()
    )
    loop_id = created["loop_id"]
    with storage.connect() as connection:
        ledger_before = connection.execute(
            "SELECT COUNT(*) FROM model_calls"
        ).fetchone()[0]

    response = created
    cycle_receipts: list[SixAgentCycleReceipt] = []
    for ordinal in range(1, 4):
        response = service.advance(
            session_id=SESSION,
            loop_id=loop_id,
            idempotency_key=f"functional-positive-advance-{ordinal:04d}",
            expected_revision=response["revision"],
        )
        state = service.state(session_id=SESSION, loop_id=loop_id)
        cycle_receipts.append(state.six_agent_cycle_receipt)
        assert state.six_agent_cycle_receipt.cycle_kind == "observation"
        assert len(state.six_agent_cycle_receipt.agent_ids) == 6
        assert len(state.six_agent_cycle_receipt.deterministic_gate_ids) == 3
        assert state.six_agent_cycle_receipt.transport_mode == (
            "deterministic_test_double"
        )
        assert state.six_agent_cycle_receipt.model_calls == 0
        assert state.six_agent_cycle_receipt.provider_calls == 0
        assert state.six_agent_cycle_receipt.cost_status == "exact"
        assert state.six_agent_cycle_receipt.cost_usd == 0.0
        assert {
            value["actor_type"]
            for value in state.six_agent_graph_audit["agents"]
        } == {"deterministic_structured_agent"}

    state = service.state(session_id=SESSION, loop_id=loop_id)
    assert [
        entry.action.evidence_item_id for entry in state.action_history
    ] == [
        "recurrence_chronology",
        "technical_assessment",
        "building_envelope",
    ]
    assert [entry.outcome for entry in state.action_history] == [
        "observed",
        "observed",
        "observed",
    ]
    assert state.phase.value == "decision_ready"
    assert state.terminal_mode == "finalize"
    assert state.blocking_uncertainty_fact_ids == ()
    assert len({value.receipt_sha256 for value in cycle_receipts}) == 3

    packet = service.packet(session_id=SESSION, loop_id=loop_id)
    audit = service.audit(session_id=SESSION, loop_id=loop_id)
    accepted = state.accepted_cycle_artifacts
    roles = accepted.role_artifacts
    role_values = {
        "canonical_facts": list(roles.canonical_facts),
        "orchestrator_plan": roles.orchestrator_plan,
        "document_source_integrity": roles.document_source_integrity,
        "process_decision_mapping": roles.process_decision_mapping,
        "evidence_checklist": roles.evidence_checklist,
        "final_claim_brief_audit": roles.final_claim_brief_audit,
    }
    assert roles.canonical_facts == accepted.facts
    assert roles.final_claim_brief_audit == accepted.final_claim_brief
    for agent in state.six_agent_graph_audit["agents"]:
        assert agent["output_artifact_hash"] == digest_value(
            role_values[agent["agent_id"]]
        )
    assert state.six_agent_cycle_receipt.accepted_cycle_artifacts_sha256 == (
        accepted.receipt_sha256
    )
    assert state.six_agent_cycle_receipt.facts_sha256 == digest_value(
        list(accepted.facts)
    )
    assert state.six_agent_cycle_receipt.process_sha256 == digest_value(
        accepted.process
    )
    assert state.six_agent_cycle_receipt.checklist_sha256 == digest_value(
        accepted.checklist
    )
    assert state.six_agent_cycle_receipt.final_claim_brief_sha256 == (
        digest_value(accepted.final_claim_brief)
    )
    assert state.six_agent_cycle_receipt.verification_sha256 == digest_value(
        accepted.verification
    )
    assert state.six_agent_cycle_receipt.graph_audit_sha256 == digest_value(
        state.six_agent_graph_audit
    )
    final_event = service.store.events(session_id=SESSION, loop_id=loop_id)[-1]
    assert final_event.event_type == "OBSERVATION_INGESTED"
    assert final_event.command["accepted_cycle_artifacts"] == (
        accepted.model_dump(mode="json")
    )
    assert final_event.command_sha256 == digest_value(final_event.command)
    assert final_event.resulting_state_sha256 == state.state_sha256
    with service.store.connect() as connection:
        checkpoint = connection.execute(
            """SELECT revision,last_event_sha256,state_sha256,state_json
            FROM claim_loop_checkpoints WHERE session_id=? AND loop_id=?""",
            (SESSION, loop_id),
        ).fetchone()
        assert checkpoint is not None
        assert checkpoint["revision"] == state.revision
        assert checkpoint["last_event_sha256"] == final_event.event_sha256
        assert checkpoint["state_sha256"] == state.state_sha256
        assert json.loads(checkpoint["state_json"]) == state.model_dump(
            mode="json"
        )
        connection.execute(
            "DELETE FROM claim_loop_checkpoints WHERE session_id=? AND loop_id=?",
            (SESSION, loop_id),
        )
    restarted = ClaimLoopService(
        storage,
        artifact_interpreter=DeterministicMouldArtifactInterpreter(),
        cycle_pipeline=_cycle_pipeline(storage),
        cycle_transport_mode="deterministic_test_double",
    )
    recovered = restarted.state(session_id=SESSION, loop_id=loop_id)
    assert canonical_json_bytes(recovered.model_dump(mode="json")) == (
        canonical_json_bytes(state.model_dump(mode="json"))
    )
    assert canonical_json_bytes(
        restarted.packet(session_id=SESSION, loop_id=loop_id)
    ) == canonical_json_bytes(packet)
    assert packet["source_state_sha256"] == state.state_sha256
    assert packet["six_agent_cycle_receipt_sha256"] == (
        state.six_agent_cycle_receipt.receipt_sha256
    )
    assert packet["deterministic_gate_receipt_sha256"] == (
        state.deterministic_gate_receipt["receipt_sha256"]
    )
    assert packet["packet_sha256"] == digest_value(
        {key: value for key, value in packet.items() if key != "packet_sha256"}
    )
    assert audit["state_sha256"] == state.state_sha256
    assert audit["total_bound_activity"]["model_calls"] == 0
    assert audit["total_bound_activity"]["provider_calls"] == 0
    assert audit["total_bound_activity"]["cost_status"] == "exact"
    assert audit["total_bound_activity"]["cost_usd"] == 0.0
    with storage.connect() as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM model_calls"
        ).fetchone()[0] == ledger_before


@pytest.mark.parametrize(
    ("agent_id", "role_field"),
    [
        ("canonical_facts", "canonical_facts"),
        ("orchestrator_plan", "orchestrator_plan"),
        ("document_source_integrity", "document_source_integrity"),
        ("process_decision_mapping", "process_decision_mapping"),
        ("evidence_checklist", "evidence_checklist"),
        ("final_claim_brief_audit", "final_claim_brief_audit"),
    ],
)
def test_fully_rehashed_invalid_role_artifact_is_rejected(
    tmp_path: Path,
    agent_id: str,
    role_field: str,
) -> None:
    _, service, created, _ = _fixture(tmp_path)
    state = service.state(session_id=SESSION, loop_id=created["loop_id"])
    accepted = state.accepted_cycle_artifacts
    roles_payload = accepted.role_artifacts.model_dump(
        mode="json", exclude={"receipt_sha256"}
    )
    forged_value: Any = (
        [{"fact_id": "forged"}]
        if role_field == "canonical_facts"
        else {"forged": True}
    )
    roles_payload[role_field] = forged_value
    forged_roles = type(accepted.role_artifacts).model_validate(
        {
            **roles_payload,
            "receipt_sha256": digest_value(roles_payload),
        }
    )
    accepted_payload = accepted.model_dump(
        mode="json", exclude={"receipt_sha256"}
    )
    accepted_payload["role_artifacts"] = forged_roles.model_dump(mode="json")
    if role_field == "canonical_facts":
        accepted_payload["facts"] = forged_value
    elif role_field == "final_claim_brief_audit":
        accepted_payload["final_claim_brief"] = forged_value
    forged_accepted = type(accepted).model_validate(
        {
            **accepted_payload,
            "receipt_sha256": digest_value(accepted_payload),
        }
    )
    graph = deepcopy(state.six_agent_graph_audit)
    if role_field != "canonical_facts":
        graph["specialist_artifacts"][role_field] = forged_value
    if role_field == "final_claim_brief_audit":
        graph["final_claim_brief"] = forged_value
    agent = next(value for value in graph["agents"] if value["agent_id"] == agent_id)
    agent["output_artifact_hash"] = digest_value(forged_value)

    with pytest.raises(ClaimLoopCycleError, match="artifact"):
        validate_accepted_role_artifacts_v1(
            accepted_cycle_artifacts=forged_accepted,
            graph_audit=graph,
        )


def test_unavailable_evidence_replans_then_abstains_without_expiry(
    tmp_path: Path,
) -> None:
    adapter = CountingUnavailableAdapter()
    _, service, created, _ = _fixture(tmp_path, adapter=adapter)
    response = created
    for ordinal in range(1, 5):
        response = service.advance(
            session_id=SESSION,
            loop_id=created["loop_id"],
            idempotency_key=f"functional-unavailable-advance-{ordinal:04d}",
            expected_revision=response["revision"],
        )

    state = service.state(session_id=SESSION, loop_id=created["loop_id"])
    assert [
        entry.action.evidence_item_id for entry in state.action_history
    ] == [
        "recurrence_chronology",
        "technical_assessment",
        "moisture_measurements",
        "building_envelope",
    ]
    assert all(entry.outcome == "unavailable" for entry in state.action_history)
    assert len({entry.action.action_sha256 for entry in state.action_history}) == 4
    assert state.phase.value == "abstained"
    assert state.terminal_mode == "abstain"
    assert state.abstain_reason == (
        "mandatory evidence is unresolved and no bounded action remains"
    )
    assert adapter.calls == 4
    assert state.active_dispatch_sha256 is None


def test_ecab_replay_seam_maps_only_sanitized_outcome_free_spans(
    tmp_path: Path,
) -> None:
    _, service, created, _ = _fixture(tmp_path)
    service.select_action(
        session_id=SESSION,
        loop_id=created["loop_id"],
        idempotency_key="ecab-seam-select-0001",
        expected_revision=created["revision"],
    )
    state = service.state(session_id=SESSION, loop_id=created["loop_id"])
    assert state.selected_action is not None
    action_payload = state.selected_action.model_dump(
        mode="json", exclude={"action_id", "action_sha256"}
    )
    action_payload["bounded_tool_id"] = ECAB_FACTUAL_HISTORY_TOOL_ID
    action_sha256 = digest_value(action_payload)
    action = type(state.selected_action).model_validate(
        {
            **action_payload,
            "action_id": f"action.{action_sha256}",
            "action_sha256": action_sha256,
        }
    )
    page = "On 20 March the customer reported that the condition had recurred."
    excerpt = "the condition had recurred"
    start = page.index(excerpt)
    span = build_ecab_factual_history_span_v1(
        event_index=0,
        previous_event_sha256=None,
        action_id=action.action_id,
        action_sha256=action.action_sha256,
        source_id="ecab-public-history.synthetic-001",
        source_sha256=digest_text(page),
        source_version=state.record_version,
        page=1,
        sanitized_page_text=page,
        text_start=start,
        text_end=start + len(excerpt),
        observed_at="2026-08-28T12:00:00+00:00",
    )

    mapped = map_ecab_factual_history_span_v1(
        action=action,
        span=span,
        record_version=state.record_version,
        expected_event_index=0,
        expected_previous_event_sha256=None,
    )

    assert mapped.action_id == action.action_id
    assert mapped.source_id == span.source_id
    assert mapped.sanitized_excerpt == excerpt
    assert mapped.span_sha256 == digest_text(excerpt)
    assert not hasattr(mapped, "observation")
    assert mapped.mapped_event_sha256 == digest_value(
        mapped.model_dump(mode="json", exclude={"mapped_event_sha256"})
    )


@pytest.mark.parametrize("forgery", ["label", "outcome", "action", "page", "order"])
def test_ecab_replay_seam_rejects_privilege_and_binding_forgery(
    tmp_path: Path,
    forgery: str,
) -> None:
    _, service, created, _ = _fixture(tmp_path / forgery)
    service.select_action(
        session_id=SESSION,
        loop_id=created["loop_id"],
        idempotency_key=f"ecab-negative-select-{forgery}",
        expected_revision=created["revision"],
    )
    state = service.state(session_id=SESSION, loop_id=created["loop_id"])
    action_payload = state.selected_action.model_dump(
        mode="json", exclude={"action_id", "action_sha256"}
    )
    action_payload["bounded_tool_id"] = ECAB_FACTUAL_HISTORY_TOOL_ID
    action_sha256 = digest_value(action_payload)
    action = type(state.selected_action).model_validate(
        {
            **action_payload,
            "action_id": f"action.{action_sha256}",
            "action_sha256": action_sha256,
        }
    )
    page = "Synthetic factual history only."
    values: dict[str, Any] = {
        "event_index": 0,
        "previous_event_sha256": None,
        "action_id": action.action_id,
        "action_sha256": action.action_sha256,
        "source_id": "ecab-public-history.synthetic-negative",
        "source_sha256": digest_text(page),
        "source_version": state.record_version,
        "page": 1,
        "sanitized_page_text": page,
        "text_start": 0,
        "text_end": len(page),
        "observed_at": "2026-08-28T12:00:00+00:00",
    }
    if forgery in {"label", "outcome"}:
        values[forgery] = "forbidden"
        with pytest.raises(ValidationError, match="Extra inputs"):
            build_ecab_factual_history_span_v1(**values)
        return
    if forgery == "page":
        values["page"] = 2
        with pytest.raises(ValidationError):
            build_ecab_factual_history_span_v1(**values)
        return
    span = build_ecab_factual_history_span_v1(**values)
    if forgery == "action":
        forged_payload = action.model_dump(
            mode="json", exclude={"action_id", "action_sha256"}
        )
        forged_payload["title"] = "Another bounded action"
        forged_hash = digest_value(forged_payload)
        action = type(action).model_validate(
            {
                **forged_payload,
                "action_id": f"action.{forged_hash}",
                "action_sha256": forged_hash,
            }
        )
    with pytest.raises(ECABReplayContractError):
        map_ecab_factual_history_span_v1(
            action=action,
            span=span,
            record_version=state.record_version,
            expected_event_index=1 if forgery == "order" else 0,
            expected_previous_event_sha256=(
                "a" * 64 if forgery == "order" else None
            ),
        )


def test_ecab_replay_module_has_no_runtime_or_data_access_imports() -> None:
    module_path = Path(__file__).parents[1] / "casepath_api" / "ecab_replay_adapter.py"
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    imported = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        (node.module or "").split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    assert imported.isdisjoint(
        {
            "requests",
            "httpx",
            "urllib",
            "socket",
            "subprocess",
            "pathlib",
            "storage",
            "claim_loop_store",
            "claim_loop_service",
            "pipeline_v15",
            "multi_agent",
        }
    )


@pytest.mark.parametrize("missing_cost", [False, True])
def test_model_source_activity_is_separate_from_deterministic_revalidation(
    tmp_path: Path,
    missing_cost: bool,
) -> None:
    storage, service, created, clock = _fixture(tmp_path)
    first = service.state(session_id=SESSION, loop_id=created["loop_id"])
    model_audit = _model_graph_audit(
        first.six_agent_graph_audit, missing_cost=missing_cost
    )
    _replace_source_run_audit(
        storage,
        run_id=first.source_run_id,
        audit=model_audit,
    )
    with storage.connect() as connection:
        ledger_before = connection.execute(
            "SELECT COUNT(*) FROM model_calls"
        ).fetchone()[0]
    service = ClaimLoopService(
        storage,
        cycle_pipeline=_cycle_pipeline(storage),
        cycle_transport_mode="deterministic_test_double",
        clock=clock,
    )
    created = service.create(
        session_id=SESSION,
        source_run_id=first.source_run_id,
        idempotency_key=f"create-activity-revalidation-{missing_cost}",
    )
    state = service.state(session_id=SESSION, loop_id=created["loop_id"])

    assert state.upstream_source_run_activity.graph_traversal_count == 1
    assert state.upstream_source_run_activity.model_calls == 6
    assert state.upstream_source_run_activity.provider_calls == 6
    assert state.upstream_source_run_activity.credential_access_status == (
        "not_measured"
    )
    assert state.source_acceptance_activity.graph_traversal_count == 1
    assert state.source_acceptance_activity.model_calls == 0
    assert state.source_acceptance_activity.provider_calls == 0
    assert state.source_acceptance_activity.credential_access_status == (
        "none_due_to_zero_provider_calls"
    )
    assert state.upstream_source_run_activity.execution_identity_sha256s != (
        state.source_acceptance_activity.execution_identity_sha256s
    )
    assert state.total_bound_activity.graph_traversal_count == 2
    assert state.total_bound_activity.model_calls == 6
    assert state.total_bound_activity.provider_calls == 6
    if missing_cost:
        assert state.upstream_source_run_activity.cost_status == "unknown"
        assert state.upstream_source_run_activity.cost_usd is None
        assert state.total_bound_activity.cost_status == "unknown"
        assert state.total_bound_activity.cost_usd is None
    else:
        assert state.upstream_source_run_activity.cost_status == "exact"
        assert state.upstream_source_run_activity.cost_usd == 0.021
        assert state.total_bound_activity.cost_status == "exact"
        assert state.total_bound_activity.cost_usd == 0.021
    with storage.connect() as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM model_calls"
        ).fetchone()[0] == ledger_before


def test_exact_source_graph_reuse_is_counted_once_not_twice(tmp_path: Path) -> None:
    storage, service, created, clock = _fixture(tmp_path)
    first = service.state(session_id=SESSION, loop_id=created["loop_id"])
    source_verification = deepcopy(first.six_agent_verification)
    source_verification["accepted_artifacts"] = [
        "canonical_claim_state",
        "legal_context",
        "process_graph",
        "evidence_model",
        "precedents",
    ]
    model_audit = _model_graph_audit(first.six_agent_graph_audit)
    whole_gate = next(
        value
        for value in model_audit["deterministic_gates"]
        if value["agent_id"] == "whole_playbook_gate"
    )
    whole_gate["verification_report_hash"] = accepted_artifact_hash(
        source_verification
    )
    whole_gate["verification_whole_playbook_hash"] = source_verification[
        "whole_playbook_hash"
    ]
    _replace_source_run_audit(
        storage,
        run_id=first.source_run_id,
        audit=model_audit,
        verification=source_verification,
    )
    alias_service = ClaimLoopService(
        storage,
        cycle_pipeline=None,
        cycle_transport_mode="deterministic_test_double",
        clock=clock,
    )
    created = alias_service.create(
        session_id=SESSION,
        source_run_id=first.source_run_id,
        idempotency_key="create-exact-source-alias-0002",
    )
    state = alias_service.state(
        session_id=SESSION, loop_id=created["loop_id"]
    )

    assert state.six_agent_cycle_receipt.transport_mode == "accepted_source_run"
    assert state.upstream_source_run_activity.execution_identity_sha256s == (
        state.source_acceptance_activity.execution_identity_sha256s
    )
    assert state.upstream_source_run_activity.model_calls == 6
    assert state.source_acceptance_activity.model_calls == 6
    assert state.total_bound_activity.graph_traversal_count == 1
    assert state.total_bound_activity.model_calls == 6
    assert state.total_bound_activity.provider_calls == 6
    assert state.total_bound_activity.cost_status == "exact"
    assert state.total_bound_activity.cost_usd == 0.021


def test_model_graph_activity_requires_complete_explicit_provenance(
    tmp_path: Path,
) -> None:
    _, service, created, _ = _fixture(tmp_path)
    state = service.state(session_id=SESSION, loop_id=created["loop_id"])
    valid = _model_graph_audit(state.six_agent_graph_audit)
    assert service._graph_activity(valid) == (6, "exact", 0.021)

    invalid_audits: list[dict[str, Any]] = []
    missing_call_count = deepcopy(valid)
    missing_call_count["agents"][0].pop("call_count")
    invalid_audits.append(missing_call_count)
    invalid_call_count = deepcopy(valid)
    invalid_call_count["agents"][0]["call_count"] = True
    invalid_audits.append(invalid_call_count)
    missing_model = deepcopy(valid)
    missing_model["agents"][0].pop("model")
    invalid_audits.append(missing_model)
    missing_provider = deepcopy(valid)
    missing_provider["agents"][0].pop("provider")
    invalid_audits.append(missing_provider)
    partial_roster = deepcopy(valid)
    partial_roster["agents"].pop()
    invalid_audits.append(partial_roster)

    for audit in invalid_audits:
        with pytest.raises(ClaimLoopServiceError):
            service._graph_activity(audit)


def test_cycle_receipt_activity_is_rederived_from_bound_graph_audit(
    tmp_path: Path,
) -> None:
    _, service, created, _ = _fixture(tmp_path)
    state = service.state(session_id=SESSION, loop_id=created["loop_id"])
    model_audit = _model_graph_audit(state.six_agent_graph_audit)
    payload = state.six_agent_cycle_receipt.model_dump(
        mode="json", exclude={"receipt_sha256"}
    )
    payload.update(
        {
            "transport_mode": "accepted_source_run",
            "graph_audit_sha256": digest_value(model_audit),
            "agent_receipt_sha256s": [
                digest_value(value) for value in model_audit["agents"]
            ],
            "gate_receipt_sha256s": [
                digest_value(value)
                for value in model_audit["deterministic_gates"]
            ],
        }
    )
    forged = SixAgentCycleReceipt.model_validate(
        {**payload, "receipt_sha256": digest_value(payload)}
    )
    with pytest.raises(
        ClaimLoopCycleError, match="differs from its persisted graph audit"
    ):
        validate_cycle_receipt_graph_binding_v1(
            receipt=forged, graph_audit=model_audit
        )


def test_loop_created_rederives_upstream_activity_from_persisted_audit(
    tmp_path: Path,
) -> None:
    _, service, created, _ = _fixture(tmp_path)
    event = service.store.events(
        session_id=SESSION, loop_id=created["loop_id"]
    )[0]
    command = deepcopy(event.command)
    command["upstream_source_graph_audit"] = _model_graph_audit(
        command["six_agent_graph_audit"]
    )
    with pytest.raises(
        ClaimLoopError, match="upstream source activity does not match"
    ):
        reduce_claim_loop_event(
            None,
            event_type="LOOP_CREATED",
            command=command,
            sequence=1,
            event_sha256=event.event_sha256,
            timestamp=event.created_at,
        )


def test_startup_reconciler_binds_durable_lineage_without_client_retry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage, service, created, clock = _fixture(tmp_path)
    original_complete = service.store.complete_client_request

    def crash_before_result_binding(**_: Any) -> dict[str, Any]:
        raise ClaimLoopStoreError("injected post-event crash")

    monkeypatch.setattr(
        service.store, "complete_client_request", crash_before_result_binding
    )
    with pytest.raises(ClaimLoopServiceError, match="post-event crash"):
        service.select_action(
            session_id=SESSION,
            loop_id=created["loop_id"],
            idempotency_key="reconcile-durable-lineage-0001",
            expected_revision=created["revision"],
        )
    monkeypatch.setattr(
        service.store, "complete_client_request", original_complete
    )
    restarted = ClaimLoopService(
        storage,
        cycle_pipeline=_cycle_pipeline(storage),
        cycle_transport_mode="deterministic_test_double",
        clock=clock,
    )

    receipt = restarted.reconcile_abandoned_requests(now=clock())

    assert receipt["completed_lineage"] == 1
    assert receipt["domain_events_appended"] == 0
    assert receipt["tool_calls"] == 0
    assert receipt["model_calls"] == 0
    replay = restarted.select_action(
        session_id=SESSION,
        loop_id=created["loop_id"],
        idempotency_key="reconcile-durable-lineage-0001",
        expected_revision=created["revision"],
    )
    assert replay["selected_action"] is not None
    binding = restarted.store.client_request(
        session_id=SESSION,
        loop_id=created["loop_id"],
        idempotency_key="reconcile-durable-lineage-0001",
        request_type="select_action",
        request_sha256=digest_value({"expected_revision": created["revision"]}),
    )
    assert binding["status"] == "COMPLETED"
    assert _bytes(replay) == _bytes(binding["response"])


def test_reconciler_completes_reserved_prefix_noop_after_later_tail(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = CountingUnavailableAdapter()
    _, service, created, clock = _fixture(tmp_path, adapter=adapter)
    selected = service.select_action(
        session_id=SESSION,
        loop_id=created["loop_id"],
        idempotency_key="reconcile-noop-select-0001",
        expected_revision=created["revision"],
    )
    noop_request = {"expected_revision": selected["revision"]}
    service._bind_client_request(
        session_id=SESSION,
        loop_id=created["loop_id"],
        idempotency_key="reconcile-noop-reserved-0002",
        request_type="select_action",
        request=noop_request,
    )
    reserved_state = service.state(
        session_id=SESSION, loop_id=created["loop_id"]
    )
    original_reconcile = service.reconcile_abandoned_requests
    monkeypatch.setattr(
        service,
        "reconcile_abandoned_requests",
        lambda **_: {"contract": "injected-noop"},
    )
    service.advance(
        session_id=SESSION,
        loop_id=created["loop_id"],
        idempotency_key="reconcile-noop-tail-0003",
        expected_revision=selected["revision"],
    )
    monkeypatch.setattr(
        service, "reconcile_abandoned_requests", original_reconcile
    )

    receipt = service.reconcile_abandoned_requests(now=clock())

    assert receipt["completed_noop"] == 1
    replay = service.select_action(
        session_id=SESSION,
        loop_id=created["loop_id"],
        idempotency_key="reconcile-noop-reserved-0002",
        expected_revision=selected["revision"],
    )
    assert replay["revision"] == reserved_state.revision
    assert replay["state_sha256"] == reserved_state.state_sha256
    assert adapter.calls == 1


def test_reconciler_terminalizes_expired_unstarted_and_preserves_partial_lineage(
    tmp_path: Path,
) -> None:
    _, service, created, clock = _fixture(
        tmp_path, adapter=RaisingAdapter()
    )
    mutation_request = {"expected_revision": created["revision"]}
    mutation = service._bind_client_request(
        session_id=SESSION,
        loop_id=created["loop_id"],
        idempotency_key="reconcile-expired-mutation-0001",
        request_type="select_action",
        request=mutation_request,
    )
    prejournal_loop = "loop.prejournal-reconciliation-0001"
    prejournal = service._bind_client_request(
        session_id=SESSION,
        loop_id=prejournal_loop,
        idempotency_key="reconcile-expired-create-0001",
        request_type="create",
        request={"source_run_id": "run.never-created"},
    )
    with pytest.raises(RuntimeError, match="tool-process crash"):
        service.advance(
            session_id=SESSION,
            loop_id=created["loop_id"],
            idempotency_key="reconcile-partial-dispatch-0001",
            expected_revision=created["revision"],
        )
    active_receipt = service.reconcile_abandoned_requests(now=clock())
    assert active_receipt["active_reserved"] == 3
    assert active_receipt["superseded"] == 0
    assert active_receipt["abandoned"] == 0
    clock.advance(seconds=ClaimLoopService.CLIENT_REQUEST_TTL_SECONDS + 1)

    receipt = service.reconcile_abandoned_requests(now=clock())

    assert receipt["superseded"] == 1
    assert receipt["abandoned"] == 1
    assert receipt["active_partial_lineage"] == 1
    superseded = service.store.client_request(
        session_id=SESSION,
        loop_id=created["loop_id"],
        idempotency_key="reconcile-expired-mutation-0001",
        request_type="select_action",
        request_sha256=mutation["request_sha256"],
    )
    abandoned = service.store.client_request(
        session_id=SESSION,
        loop_id=prejournal_loop,
        idempotency_key="reconcile-expired-create-0001",
        request_type="create",
        request_sha256=prejournal["request_sha256"],
    )
    partial = service.store.client_request(
        session_id=SESSION,
        loop_id=created["loop_id"],
        idempotency_key="reconcile-partial-dispatch-0001",
        request_type="advance",
        request_sha256=digest_value(
            {
                "expected_revision": created["revision"],
                "requested_adapter_id": None,
            }
        ),
    )
    assert superseded["status"] == "SUPERSEDED"
    assert abandoned["status"] == "ABANDONED"
    assert partial["status"] == "RESERVED"


def test_fastapi_raw_replays_are_stable_after_tail_and_restart(
    tmp_path: Path,
) -> None:
    storage, service, created, clock = _fixture(tmp_path)
    adapters: dict[str, object] = {
        DEFAULT_EVIDENCE_TOOL_ID: SyntheticMouldEvidenceAdapter()
    }
    headers = {
        "X-CasePath-Session": SESSION,
        "X-CasePath-Idempotency-Key": "api-success-advance-0001",
    }
    client = _claim_loop_test_client(
        storage=storage, clock=clock, adapters=adapters
    )
    first = client.post(
        f"/api/claim-loops/v1/{created['loop_id']}/advance",
        headers=headers,
        json={"expected_revision": created["revision"]},
    )
    assert first.status_code == 200
    first_bytes = first.content
    later_headers = {
        **headers,
        "X-CasePath-Idempotency-Key": "api-success-advance-0002",
    }
    later = client.post(
        f"/api/claim-loops/v1/{created['loop_id']}/advance",
        headers=later_headers,
        json={"expected_revision": first.json()["revision"]},
    )
    assert later.status_code == 200
    client.close()
    restarted = _claim_loop_test_client(
        storage=storage, clock=clock, adapters=adapters
    )
    replay = restarted.post(
        f"/api/claim-loops/v1/{created['loop_id']}/advance",
        headers=headers,
        json={"expected_revision": created["revision"]},
    )
    assert replay.status_code == 200
    assert replay.content == first_bytes
    restarted.close()

    source_run_id = service.state(
        session_id=SESSION, loop_id=created["loop_id"]
    ).source_run_id
    noop_created = service.create(
        session_id=SESSION,
        source_run_id=source_run_id,
        idempotency_key="api-noop-create-0001",
    )
    selected = service.select_action(
        session_id=SESSION,
        loop_id=noop_created["loop_id"],
        idempotency_key="api-noop-select-0001",
        expected_revision=noop_created["revision"],
    )
    adapters.clear()
    noop_headers = {
        "X-CasePath-Session": SESSION,
        "X-CasePath-Idempotency-Key": "api-noop-advance-0001",
    }
    client = _claim_loop_test_client(
        storage=storage, clock=clock, adapters=adapters
    )
    noop = client.post(
        f"/api/claim-loops/v1/{noop_created['loop_id']}/advance",
        headers=noop_headers,
        json={"expected_revision": selected["revision"]},
    )
    assert noop.status_code == 200
    noop_bytes = noop.content
    adapters[DEFAULT_EVIDENCE_TOOL_ID] = SyntheticMouldEvidenceAdapter()
    tail = client.post(
        f"/api/claim-loops/v1/{noop_created['loop_id']}/advance",
        headers={
            **noop_headers,
            "X-CasePath-Idempotency-Key": "api-noop-tail-0002",
        },
        json={"expected_revision": selected["revision"]},
    )
    assert tail.status_code == 200
    client.close()
    restarted = _claim_loop_test_client(
        storage=storage, clock=clock, adapters=adapters
    )
    noop_replay = restarted.post(
        f"/api/claim-loops/v1/{noop_created['loop_id']}/advance",
        headers=noop_headers,
        json={"expected_revision": selected["revision"]},
    )
    assert noop_replay.status_code == 200
    assert noop_replay.content == noop_bytes
    restarted.close()

    crash_created = service.create(
        session_id=SESSION,
        source_run_id=source_run_id,
        idempotency_key="api-crash-create-0001",
    )
    raising = SwitchableEvidenceAdapter()
    raising.configure_raise()
    adapters[DEFAULT_EVIDENCE_TOOL_ID] = raising
    crash_headers = {
        "X-CasePath-Session": SESSION,
        "X-CasePath-Idempotency-Key": "api-crash-advance-0001",
    }
    client = _claim_loop_test_client(
        storage=storage,
        clock=clock,
        adapters=adapters,
        raise_server_exceptions=False,
    )
    crashed = client.post(
        f"/api/claim-loops/v1/{crash_created['loop_id']}/advance",
        headers=crash_headers,
        json={"expected_revision": crash_created["revision"]},
    )
    assert crashed.status_code == 500
    assert raising.calls == 1
    client.close()
    raising.configure_observed()
    recovery_service = ClaimLoopService(
        storage,
        adapters={DEFAULT_EVIDENCE_TOOL_ID: raising},
        artifact_interpreter=DeterministicMouldArtifactInterpreter(),
        cycle_pipeline=_cycle_pipeline(storage),
        cycle_transport_mode="deterministic_test_double",
        clock=clock,
    )
    dispatch_state = recovery_service._raw_state(
        session_id=SESSION, loop_id=crash_created["loop_id"]
    )
    synthetic = raising.execute(
        action=dispatch_state.selected_action,
        state=dispatch_state,
        idempotency_key=dispatch_state.active_dispatch_sha256,
        timestamp=clock(),
    )
    _register_observed_artifact(
        recovery_service, dispatch_state, synthetic, timestamp=clock()
    )
    adapters[DEFAULT_EVIDENCE_TOOL_ID] = raising
    restarted = _claim_loop_test_client(
        storage=storage, clock=clock, adapters=adapters
    )
    recovered = restarted.post(
        f"/api/claim-loops/v1/{crash_created['loop_id']}/advance",
        headers=crash_headers,
        json={"expected_revision": crash_created["revision"]},
    )
    assert recovered.status_code == 200
    recovered_bytes = recovered.content
    crash_tail = restarted.post(
        f"/api/claim-loops/v1/{crash_created['loop_id']}/advance",
        headers={
            **crash_headers,
            "X-CasePath-Idempotency-Key": "api-crash-tail-0002",
        },
        json={"expected_revision": recovered.json()["revision"]},
    )
    assert crash_tail.status_code == 200
    restarted.close()
    restarted = _claim_loop_test_client(
        storage=storage, clock=clock, adapters=adapters
    )
    recovered_replay = restarted.post(
        f"/api/claim-loops/v1/{crash_created['loop_id']}/advance",
        headers=crash_headers,
        json={"expected_revision": crash_created["revision"]},
    )
    assert recovered_replay.status_code == 200
    assert recovered_replay.content == recovered_bytes
    restarted.close()

    superseded_created = service.create(
        session_id=SESSION,
        source_run_id=source_run_id,
        idempotency_key="api-superseded-create-0001",
    )
    superseded_request = {
        "expected_revision": superseded_created["revision"],
        "requested_adapter_id": None,
    }
    service._bind_client_request(
        session_id=SESSION,
        loop_id=superseded_created["loop_id"],
        idempotency_key="api-superseded-advance-0001",
        request_type="advance",
        request=superseded_request,
    )
    service.advance(
        session_id=SESSION,
        loop_id=superseded_created["loop_id"],
        idempotency_key="api-superseded-tail-0002",
        expected_revision=superseded_created["revision"],
    )
    superseded_headers = {
        "X-CasePath-Session": SESSION,
        "X-CasePath-Idempotency-Key": "api-superseded-advance-0001",
    }
    client = _claim_loop_test_client(
        storage=storage, clock=clock, adapters=adapters
    )
    conflict = client.post(
        f"/api/claim-loops/v1/{superseded_created['loop_id']}/advance",
        headers=superseded_headers,
        json={"expected_revision": superseded_created["revision"]},
    )
    assert conflict.status_code == 409
    conflict_bytes = conflict.content
    assert conflict.json()["detail"]["failure_sha256"]
    client.close()
    restarted = _claim_loop_test_client(
        storage=storage, clock=clock, adapters=adapters
    )
    conflict_replay = restarted.post(
        f"/api/claim-loops/v1/{superseded_created['loop_id']}/advance",
        headers=superseded_headers,
        json={"expected_revision": superseded_created["revision"]},
    )
    assert conflict_replay.status_code == 409
    assert conflict_replay.content == conflict_bytes
    restarted.close()


def test_correction_and_reuse_terminalize_during_active_dispatch(
    tmp_path: Path,
) -> None:
    adapter = SwitchableEvidenceAdapter()
    _, service, created, _ = _fixture(
        tmp_path, adapter=adapter
    )
    source_first = service.advance(
        session_id=SESSION,
        loop_id=created["loop_id"],
        idempotency_key="active-correction-source-0001",
        expected_revision=created["revision"],
    )
    source_second = service.advance(
        session_id=SESSION,
        loop_id=created["loop_id"],
        idempotency_key="active-correction-source-0002",
        expected_revision=source_first["revision"],
    )
    source_state = service.state(session_id=SESSION, loop_id=created["loop_id"])
    source_artifact = service.store.tool_artifact(
        source_state.projection_ledger[-1].artifact_receipt_sha256
    )
    assert source_artifact is not None
    source_ref = source_artifact.observation.source_refs[0]
    correction = _admit_correction(
        service,
        session_id=SESSION,
        loop_id=created["loop_id"],
        source_artifact_receipt_sha256=source_artifact.receipt_sha256,
        effect=CorrectionEffect(
            fact_id="fact_cause",
            evidence_item_id="technical_assessment",
            value=source_ref.sanitized_excerpt,
            fact_state="conflicting",
            normalized_value=None,
            explanation="The source is internally contradictory.",
            evidence_status="provided_sufficient",
        ),
        suffix="active-dispatch",
    )

    adapter.configure_unavailable(blocking=True)
    blocker = adapter
    worker_results: list[dict[str, Any]] = []

    def advance_source() -> None:
        worker_results.append(
            service.advance(
                session_id=SESSION,
                loop_id=created["loop_id"],
                idempotency_key="active-correction-dispatch-0003",
                expected_revision=source_second["revision"],
            )
        )

    thread = threading.Thread(target=advance_source)
    thread.start()
    assert blocker.entered.wait(timeout=5)
    event_count = len(
        service.store.events(session_id=SESSION, loop_id=created["loop_id"])
    )
    conflicts: list[dict[str, Any]] = []
    for _ in range(2):
        with pytest.raises(ClaimLoopServiceError) as raised:
            service.apply_correction(
                session_id=SESSION,
                loop_id=created["loop_id"],
                correction_id=correction.correction_id,
                idempotency_key="active-correction-apply-0001",
            )
        assert raised.value.conflict_envelope is not None
        conflicts.append(raised.value.conflict_envelope)
    assert canonical_json_bytes(conflicts[0]) == canonical_json_bytes(conflicts[1])
    assert len(
        service.store.events(session_id=SESSION, loop_id=created["loop_id"])
    ) == event_count
    blocker.release.set()
    thread.join(timeout=10)
    assert len(worker_results) == 1

    reusable_correction = _admit_correction(
        service,
        session_id=SESSION,
        loop_id=created["loop_id"],
        source_artifact_receipt_sha256=source_artifact.receipt_sha256,
        effect=CorrectionEffect(
            fact_id="fact_cause",
            evidence_item_id="technical_assessment",
            value=source_ref.sanitized_excerpt,
            fact_state="conflicting",
            normalized_value=None,
            explanation="The source remains internally contradictory.",
            evidence_status="provided_sufficient",
        ),
        suffix="active-dispatch-reuse",
    )
    service.apply_correction(
        session_id=SESSION,
        loop_id=created["loop_id"],
        correction_id=reusable_correction.correction_id,
        idempotency_key="active-correction-source-apply-0002",
    )
    target_created = service.create(
        session_id=SESSION,
        source_run_id=source_state.source_run_id,
        idempotency_key="active-reuse-target-create-0001",
    )
    adapter.configure_observed()
    target_first = service.advance(
        session_id=SESSION,
        loop_id=target_created["loop_id"],
        idempotency_key="active-reuse-target-source-0001",
        expected_revision=target_created["revision"],
    )
    target_second = service.advance(
        session_id=SESSION,
        loop_id=target_created["loop_id"],
        idempotency_key="active-reuse-target-source-0002",
        expected_revision=target_first["revision"],
    )
    adapter.configure_unavailable(blocking=True)
    blocker = adapter
    target_results: list[dict[str, Any]] = []

    def advance_target() -> None:
        target_results.append(
            service.advance(
                session_id=SESSION,
                loop_id=target_created["loop_id"],
                idempotency_key="active-reuse-dispatch-0003",
                expected_revision=target_second["revision"],
            )
        )

    thread = threading.Thread(target=advance_target)
    thread.start()
    assert blocker.entered.wait(timeout=5)
    target_event_count = len(
        service.store.events(session_id=SESSION, loop_id=target_created["loop_id"])
    )
    with pytest.raises(ClaimLoopServiceError) as raised:
        service.reuse_correction(
            session_id=SESSION,
            loop_id=target_created["loop_id"],
            correction_id=reusable_correction.correction_id,
            idempotency_key="active-reuse-apply-0001",
        )
    assert raised.value.conflict_envelope is not None
    assert len(
        service.store.events(session_id=SESSION, loop_id=target_created["loop_id"])
    ) == target_event_count
    blocker.release.set()
    thread.join(timeout=10)
    assert len(target_results) == 1
