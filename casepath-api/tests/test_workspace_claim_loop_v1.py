from __future__ import annotations

import base64
import os
import signal
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from multiprocessing import get_context
from pathlib import Path
from threading import Event

import pytest
from casepath_api.canonicalizer import MODEL_MODE_REFERENCE
from casepath_api.claim_loop_router import create_claim_loop_router
from casepath_api.claim_loop_service import ClaimLoopService
from casepath_api.claim_loop import (
    ClaimLoopError,
    CorrectionToolResult,
    derive_evidence_action_v1,
)
from casepath_api.claim_loop_contracts import (
    CorrectionArtifactReceipt,
    ScopedCorrection,
)
from casepath_api.claim_loop_store import ClaimLoopStoreError
from casepath_api.claim_workspace_intake_v1 import compile_intake_assessment
from casepath_api.claim_workspace_v1 import (
    WORKSPACE_SESSION_ID,
    ClaimWorkspaceService,
)
from casepath_api.foundation.common import canonical_json_bytes, digest_value
from casepath_api.multi_agent import (
    AI_AGENT_IDS,
    DETERMINISTIC_GATE_IDS,
    DeterministicStructuredAgent,
    NemotronMultiAgentOrchestrator,
)
from casepath_api.pipeline_v15 import ClaimPipeline
from casepath_api.storage import Storage
from casepath_api.workspace_claim_loop_v1 import (
    WORKSPACE_CLAIM_LOOP_SESSION_ID,
    WORKSPACE_EVIDENCE_ADAPTER_ID,
    DeterministicTemplateCyclePipelineRouter,
    WorkspaceClaimLoopError,
    WorkspaceClaimLoopServiceV1,
    WorkspaceEvidenceWithdrawalCorrectionAdapterV1,
)
from casepath_api.workspace_corpus import (
    PublicCorpus,
    WorkspaceCorpusError,
    default_public_corpus_root,
    default_workspace_corpus_root,
)
from casepath_api.workspace_evidence_authority_v1 import (
    EVIDENCE_REGISTRATION_FIELDS,
    EVIDENCE_REGISTRATION_SCHEMA,
    LoopbackSourceByteAcquisitionAdapterV1,
    ServerInterpretedWorkspaceEvidenceV1,
    WorkspaceEvidenceAuthorityError,
)
from fastapi import FastAPI
from fastapi.testclient import TestClient


def _system(
    root: Path,
    *,
    corpus: PublicCorpus | None = None,
) -> tuple[
    Storage,
    ClaimWorkspaceService,
    ClaimLoopService,
    WorkspaceClaimLoopServiceV1,
]:
    storage = Storage(str(root / "casepath.db"))
    corpus = corpus or PublicCorpus(default_public_corpus_root())
    workspace = ClaimWorkspaceService(storage, corpus=corpus)
    default_pipeline = ClaimPipeline(
        storage,
        model_mode=MODEL_MODE_REFERENCE,
        agent_orchestrator=NemotronMultiAgentOrchestrator(
            storage,
            agent_runner=DeterministicStructuredAgent(),
        ),
        pace_seconds=0,
    )
    router = DeterministicTemplateCyclePipelineRouter(storage, default_pipeline)
    adapter = LoopbackSourceByteAcquisitionAdapterV1(root / "evidence")
    interpreter = ServerInterpretedWorkspaceEvidenceV1(adapter)
    correction_adapter = WorkspaceEvidenceWithdrawalCorrectionAdapterV1()
    normal = ClaimLoopService(
        storage,
        adapters={adapter.adapter_id: adapter},
        artifact_interpreter=interpreter,
        cycle_pipeline=router,
        correction_adapters={
            correction_adapter.adapter_id: correction_adapter,
        },
        authorized_owned_sessions=(WORKSPACE_CLAIM_LOOP_SESSION_ID,),
        reconciliation_scope="authorized_only",
        cycle_transport_mode="deterministic_test_double",
    )
    facade = WorkspaceClaimLoopServiceV1(
        workspace=workspace,
        claim_loop=normal,
        pipeline_router=router,
        adapter=adapter,
        interpreter=interpreter,
        correction_adapter=correction_adapter,
    )
    return storage, workspace, normal, facade


def _started_claim(
    workspace: ClaimWorkspaceService,
) -> tuple[str, dict[str, object]]:
    workspace.seed(timestamp="2026-08-31T12:00:00+00:00")
    # Exercise the portal/plain-text source form used by the real browser
    # journey, with a server-interpretable first source span. RFC-822-only
    # fixtures do not expose source-registry grounding errors for valid
    # non-email intake messages.
    claim_id = next(
        value
        for value in sorted(workspace.corpus.bindings)
        if compile_intake_assessment(workspace.corpus, value)["claim_type"]
        == "lease_termination_dispute"
        and str(
            workspace.corpus.claim(value)["customer_message"]["raw_file"]["media_type"]
        )
        .lower()
        .startswith("text/plain")
    )
    initial = workspace.store.recover(claim_id)
    started = workspace.start(
        claim_id,
        idempotency_key="workspace.start.test.0001",
        expected_revision=initial["revision"],
        timestamp="2026-08-31T12:00:01+00:00",
    )["state"]
    return claim_id, started


def _ensure(
    facade: WorkspaceClaimLoopServiceV1,
    claim_id: str,
    started: dict[str, object],
) -> dict[str, object]:
    return facade.ensure(
        claim_id,
        expected_workspace_revision=int(started["revision"]),
        expected_workspace_state_sha256=str(started["state_sha256"]),
        idempotency_key="workspace.ensure.test." + claim_id,
    )


def _register_server_evidence(
    facade: WorkspaceClaimLoopServiceV1,
    claim_id: str,
    view: dict[str, object],
    *,
    idempotency_key: str,
    timestamp: str = "2026-08-31T12:00:02+00:00",
) -> dict[str, object]:
    loop = view["loop_state"]
    assert isinstance(loop, dict)
    action = loop["selected_action"]
    assert isinstance(action, dict)
    intent_response = facade.mint_evidence_intent(
        claim_id,
        action_id=str(action["action_id"]),
        expected_revision=int(loop["revision"]),
        idempotency_key=idempotency_key,
        timestamp=timestamp,
    )
    intent = intent_response["intent"]
    assert isinstance(intent, dict)
    acquisition_response = facade.acquire_evidence(
        claim_id,
        acquisition_intent_id=str(intent["intent_id"]),
        timestamp=timestamp,
    )
    acquisition_receipt = acquisition_response["acquisition_receipt"]
    assert isinstance(acquisition_receipt, dict)
    registration_body = {
        "schema": EVIDENCE_REGISTRATION_SCHEMA,
        "action_id": str(action["action_id"]),
        "expected_revision": int(loop["revision"]),
        "idempotency_key": idempotency_key,
        "acquisition_intent_id": str(intent["intent_id"]),
        "acquisition_receipt_id": str(acquisition_receipt["acquisition_receipt_id"]),
        "content_b64": str(acquisition_response["content_b64"]),
    }
    assert tuple(registration_body) == EVIDENCE_REGISTRATION_FIELDS
    registration_response = facade.register_evidence(
        claim_id,
        **registration_body,
        timestamp=timestamp,
    )
    return {
        "intent_response": intent_response,
        "intent": intent,
        "acquisition_response": acquisition_response,
        "acquisition_receipt": acquisition_receipt,
        "registration_body": registration_body,
        "registration_response": registration_response,
        "stage_receipt": registration_response["stage_receipt"],
        "content": base64.b64decode(
            str(acquisition_response["content_b64"]), validate=True
        ).decode("utf-8"),
    }


def _http_register_server_evidence(
    client: TestClient,
    claim_id: str,
    view: dict[str, object],
    *,
    idempotency_key: str,
) -> dict[str, object]:
    loop = view["loop_state"]
    assert isinstance(loop, dict)
    action = loop["selected_action"]
    assert isinstance(action, dict)
    intent_body = {
        "action_id": action["action_id"],
        "expected_revision": loop["revision"],
        "idempotency_key": idempotency_key,
    }
    intent_response = client.post(
        f"/api/claim-loops/v1/workspace/claims/{claim_id}/loop/evidence/intents",
        json=intent_body,
    )
    assert intent_response.status_code == 200, intent_response.text
    intent = intent_response.json()["intent"]
    acquire_path = (
        f"/api/claim-loops/v1/workspace/claims/{claim_id}/loop/evidence/intents/"
        f"{intent['intent_id']}/acquire"
    )
    acquisition_response = client.post(acquire_path)
    assert acquisition_response.status_code == 200, acquisition_response.text
    acquisition = acquisition_response.json()
    acquisition_receipt = acquisition["acquisition_receipt"]
    registration_body = {
        "schema": EVIDENCE_REGISTRATION_SCHEMA,
        "action_id": action["action_id"],
        "expected_revision": loop["revision"],
        "idempotency_key": idempotency_key,
        "acquisition_intent_id": intent["intent_id"],
        "acquisition_receipt_id": acquisition_receipt["acquisition_receipt_id"],
        "content_b64": acquisition["content_b64"],
    }
    assert tuple(registration_body) == EVIDENCE_REGISTRATION_FIELDS
    headers = {"X-CasePath-Idempotency-Key": idempotency_key}
    registration_response = client.post(
        f"/api/claim-loops/v1/workspace/claims/{claim_id}/loop/evidence",
        json=registration_body,
        headers=headers,
    )
    assert registration_response.status_code == 200, registration_response.text
    return {
        "intent_body": intent_body,
        "intent_response": intent_response,
        "intent": intent,
        "acquire_path": acquire_path,
        "acquisition_response": acquisition_response,
        "acquisition": acquisition,
        "registration_body": registration_body,
        "registration_headers": headers,
        "registration_response": registration_response,
    }


def _advance_resolved_once(
    facade: WorkspaceClaimLoopServiceV1,
    claim_id: str,
    view: dict[str, object],
    *,
    suffix: str,
) -> dict[str, object]:
    loop = view["loop_state"]
    assert isinstance(loop, dict)
    selected = loop["selected_action"]
    assert isinstance(selected, dict)
    registered = _register_server_evidence(
        facade,
        claim_id,
        view,
        idempotency_key=f"workspace.register.{suffix}",
    )
    facade.advance(
        claim_id,
        expected_revision=loop["revision"],
        expected_state_sha256=loop["state_sha256"],
        action_sha256=selected["action_sha256"],
        stage_receipt_sha256=registered["stage_receipt"]["receipt_sha256"],
        idempotency_key=f"workspace.advance.{suffix}",
    )
    return facade.view(claim_id)


def test_operational_queue_and_workbench_share_the_live_claim_journal(
    tmp_path: Path,
) -> None:
    _, workspace, _, facade = _system(tmp_path)
    claim_id, started = _started_claim(workspace)
    before = facade.queue(
        now="2026-08-31T12:00:02+00:00",
        query=claim_id,
        limit=25,
    )["items"][0]
    assert before["operational_projection"]["claim_loop_prefix"] is None
    assert before["operational_projection"]["next_state"]["kind"] == (
        "start_processing"
    )

    initial = _ensure(facade, claim_id, started)
    queue_initial = facade.queue(
        now="2026-08-31T12:00:03+00:00",
        query=claim_id,
        limit=25,
    )["items"][0]
    projection = queue_initial["operational_projection"]
    assert projection == initial["operational_projection"]
    assert projection["claim_loop_prefix"]["state_sha256"] == (
        initial["loop_state"]["state_sha256"]
    )
    assert projection["current_process"]["node_id"] == (
        initial["loop_state"]["process"]["current_overlay"]["current_node_id"]
    )
    assert projection["controlling_decision"]["evidence_item_id"] == (
        initial["loop_state"]["selected_action"]["evidence_item_id"]
    )
    assert set(projection["evidence_class_counts"]) == {
        "received",
        "missing",
        "insufficient",
        "conditional",
        "irrelevant",
        "unknown",
    }
    assert sum(projection["evidence_class_counts"].values()) == len(
        initial["loop_state"]["checklist"]["items"]
    )

    advanced = _advance_resolved_once(
        facade,
        claim_id,
        initial,
        suffix="operational-projection.0001",
    )
    queue_advanced = facade.queue(
        now="2026-08-31T12:00:04+00:00",
        query=claim_id,
        limit=25,
    )["items"][0]
    assert queue_advanced["operational_projection"] == (
        advanced["operational_projection"]
    )
    assert queue_advanced["operational_projection"]["projection_sha256"] != (
        projection["projection_sha256"]
    )
    assert queue_advanced["principal_blocker"] == (
        advanced["operational_projection"]["principal_blocker"]
    )
    assert queue_advanced["next_safe_action"] == (
        advanced["operational_projection"]["next_state"]["title"]
    )


def test_operational_queue_waits_for_a_stable_read_beyond_three_commits(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, workspace, _, facade = _system(tmp_path)
    workspace.seed(timestamp="2026-08-31T12:00:00+00:00")
    changing = [
        (1, 1, index, index, index)
        for index in range(1, 7)
    ]
    stable = (1, 1, 7, 7, 7)
    tokens = iter([*changing, stable, stable, stable])
    calls = 0

    def journal_version_token() -> tuple[int, int, int, int, int]:
        nonlocal calls
        calls += 1
        return next(tokens, stable)

    monkeypatch.setattr(
        facade.claim_loop.store,
        "journal_version_token",
        journal_version_token,
    )
    monkeypatch.setattr(
        "casepath_api.workspace_claim_loop_v1.time.sleep",
        lambda _seconds: None,
    )
    result = facade.queue(
        now="2026-08-31T12:00:01+00:00",
        sort="priority",
        limit=25,
    )
    assert result["total_count"] == 60
    assert calls == 9


def test_normal_loop_append_invalidates_an_operational_queue_cursor(
    tmp_path: Path,
) -> None:
    _, workspace, _, facade = _system(tmp_path)
    claim_id, started = _started_claim(workspace)
    initial = _ensure(facade, claim_id, started)
    first_page = facade.queue(
        now="2026-08-31T12:00:03+00:00",
        sort="priority",
        limit=1,
    )
    assert first_page["next_cursor"] is not None
    _advance_resolved_once(
        facade,
        claim_id,
        initial,
        suffix="cursor-stale.0001",
    )
    with pytest.raises(
        WorkspaceClaimLoopError,
        match="queue cursor is stale",
    ):
        facade.queue(
            cursor=first_page["next_cursor"],
            sort="priority",
            limit=1,
        )


def test_operational_queue_cache_never_hides_historical_journal_tamper(
    tmp_path: Path,
) -> None:
    _, workspace, _, facade = _system(tmp_path)
    claim_id, started = _started_claim(workspace)
    view = _ensure(facade, claim_id, started)
    facade.queue(now="2026-08-31T12:00:03+00:00", limit=100)
    facade.queue(now="2026-08-31T12:00:03+00:00", limit=100)

    with sqlite3.connect(tmp_path / "casepath.db") as connection:
        changed = connection.execute(
            """UPDATE claim_loop_events SET created_at=?
            WHERE session_id=? AND loop_id=? AND sequence=1""",
            (
                "2026-08-31T11:59:59+00:00",
                WORKSPACE_CLAIM_LOOP_SESSION_ID,
                view["loop_state"]["loop_id"],
            ),
        ).rowcount
        assert changed == 1
        connection.commit()

    with pytest.raises(WorkspaceClaimLoopError, match="claim loop event"):
        facade.queue(now="2026-08-31T12:00:04+00:00", limit=100)


def test_queue_write_reuses_unchanged_claim_loop_replays(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    corpus = PublicCorpus(default_workspace_corpus_root())
    _, workspace, normal, facade = _system(tmp_path, corpus=corpus)
    workspace.seed(timestamp="2026-08-31T12:00:00+00:00")
    claim_ids = sorted(corpus.bindings)
    for index, claim_id in enumerate(claim_ids[:2]):
        initial = workspace.store.recover(claim_id)
        started = workspace.start(
            claim_id,
            idempotency_key=f"queue-cache-start-{index}",
            expected_revision=initial["revision"],
            timestamp="2026-08-31T12:00:01+00:00",
        )["state"]
        facade.ensure(
            claim_id,
            expected_workspace_revision=started["revision"],
            expected_workspace_state_sha256=started["state_sha256"],
            idempotency_key=f"queue-cache-ensure-{index}",
        )
    assert facade.queue(now="2026-08-31T12:00:02+00:00", limit=25)["total_count"] == 150

    third = claim_ids[2]
    initial = workspace.store.recover(third)
    workspace.start(
        third,
        idempotency_key="queue-cache-start-third",
        expected_revision=initial["revision"],
        timestamp="2026-08-31T12:00:03+00:00",
    )

    def unexpected_replay(*args, **kwargs):
        raise AssertionError("an unchanged claim loop was replayed")

    monkeypatch.setattr(normal.store, "state_at_revision", unexpected_replay)
    monkeypatch.setattr(normal.store, "_replay_rows_uncached", unexpected_replay)
    assert facade.queue(now="2026-08-31T12:00:04+00:00", limit=25)["total_count"] == 150


@pytest.mark.parametrize(
    "mutation",
    ("in_place", "replace", "extra", "symlink", "remove"),
)
def test_workspace_state_cache_fails_closed_on_corpus_inventory_drift(
    tmp_path: Path,
    mutation: str,
    writable_corpus_copy,
) -> None:
    copied_root = writable_corpus_copy(
        default_public_corpus_root(), tmp_path / "corpus"
    )
    corpus = PublicCorpus(copied_root)
    storage, workspace, _, facade = _system(tmp_path, corpus=corpus)
    workspace.seed(timestamp="2026-08-31T12:00:00+00:00")
    assert len(workspace.states()) == 60
    # A second call must actually exercise the roster cache before drift.
    assert len(workspace.states()) == 60
    assert facade.queue(
        now="2026-08-31T12:00:01+00:00", limit=100
    )["total_count"] == 60

    claim_id = sorted(corpus.bindings)[0]
    target = copied_root / corpus.binding(claim_id)["claim"]["path"]
    original = target.read_bytes()
    if mutation == "in_place":
        original_stat = target.stat()
        target.write_bytes(bytes([original[0] ^ 1]) + original[1:])
        os.utime(target, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))
    elif mutation == "replace":
        replacement = target.with_name(target.name + ".replacement")
        replacement.write_bytes(original)
        os.replace(replacement, target)
    elif mutation == "extra":
        (copied_root / "unexpected-entry").write_bytes(b"unexpected")
    elif mutation == "symlink":
        (copied_root / "unexpected-link").symlink_to(target)
    elif mutation == "remove":
        target.unlink()
    else:  # pragma: no cover
        raise AssertionError(mutation)

    with pytest.raises(WorkspaceCorpusError, match="runtime inventory|inventory drifted"):
        workspace.states()
    with pytest.raises(WorkspaceCorpusError, match="runtime inventory|inventory drifted"):
        facade.queue(now="2026-08-31T12:00:02+00:00", limit=100)
    with sqlite3.connect(tmp_path / "casepath.db") as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM claim_loop_events WHERE session_id=?",
            (WORKSPACE_SESSION_ID,),
        ).fetchone()[0] == 60


def test_operational_rebuild_discards_derived_cache_and_binds_both_journals(
    tmp_path: Path,
) -> None:
    _, workspace, _, facade = _system(tmp_path)
    claim_id, started = _started_claim(workspace)
    _ensure(facade, claim_id, started)
    timestamp = "2026-08-31T12:00:05+00:00"
    facade.queue(now=timestamp, limit=100)

    with sqlite3.connect(tmp_path / "casepath.db") as connection:
        connection.row_factory = sqlite3.Row
        before_rows = [
            dict(row)
            for row in connection.execute(
                """SELECT session_id,loop_id,sequence,idempotency_key,
                command_sha256,event_sha256,event_json,created_at
                FROM claim_loop_events ORDER BY session_id,loop_id,sequence"""
            )
        ]

    cached = facade._operational_roster_cache
    assert cached is not None
    cached[3][claim_id]["principal_blocker"] = "FORGED_PROCESS_CACHE"
    receipt = facade.rebuild(timestamp=timestamp)

    items: list[dict[str, object]] = []
    cursor = None
    while True:
        page = facade.queue(
            now=timestamp if cursor is None else None,
            cursor=cursor,
            limit=100,
        )
        items.extend(page["items"])
        cursor = page["next_cursor"]
        if cursor is None:
            break
    assert len(items) == 60
    assert all(
        item["operational_projection"]["principal_blocker"]
        != "FORGED_PROCESS_CACHE"
        for item in items
    )

    workspace_roster = [
        {
            "claim_id": value["claim_id"],
            "revision": value["revision"],
            "state_sha256": value["state_sha256"],
            "last_event_sha256": value["last_event_sha256"],
        }
        for value in workspace.states()
    ]
    projection_by_claim = {
        item["claim_id"]: item["operational_projection"] for item in items
    }
    loop_roster = [
        {
            "claim_id": value,
            "claim_loop_prefix": projection_by_claim[value]["claim_loop_prefix"],
        }
        for value in sorted(projection_by_claim)
    ]
    projection_roster = [
        {
            "claim_id": value,
            "projection_sha256": projection_by_claim[value]["projection_sha256"],
        }
        for value in sorted(projection_by_claim)
    ]
    assert receipt["workspace_state_roster_sha256"] == digest_value(
        workspace_roster
    )
    assert receipt["claim_loop_prefix_roster_sha256"] == digest_value(loop_roster)
    assert receipt["operational_projection_roster_sha256"] == digest_value(
        projection_roster
    )
    assert receipt["authority"] == "workspace_and_claim_loop_events"

    with sqlite3.connect(tmp_path / "casepath.db") as connection:
        connection.row_factory = sqlite3.Row
        after_rows = [
            dict(row)
            for row in connection.execute(
                """SELECT session_id,loop_id,sequence,idempotency_key,
                command_sha256,event_sha256,event_json,created_at
                FROM claim_loop_events ORDER BY session_id,loop_id,sequence"""
            )
        ]
    assert after_rows == before_rows


def test_operational_rebuild_rejects_incomplete_or_foreign_authority_rosters(
    tmp_path: Path,
) -> None:
    missing_workspace_root = tmp_path / "missing-workspace"
    missing_workspace_root.mkdir()
    _, workspace_a, _, facade_a = _system(missing_workspace_root)
    claim_a, started_a = _started_claim(workspace_a)
    _ensure(facade_a, claim_a, started_a)
    with sqlite3.connect(missing_workspace_root / "casepath.db") as connection:
        changed = connection.execute(
            """DELETE FROM claim_loop_events
            WHERE session_id=? AND loop_id=?""",
            (WORKSPACE_SESSION_ID, started_a["loop_id"]),
        ).rowcount
        assert changed >= 1
        connection.commit()
    _, _, _, facade_a_fresh = _system(missing_workspace_root)
    with pytest.raises(WorkspaceClaimLoopError, match="workspace roster"):
        facade_a_fresh.rebuild(timestamp="2026-08-31T12:00:05+00:00")

    missing_loop_root = tmp_path / "missing-loop"
    missing_loop_root.mkdir()
    _, workspace_b, _, facade_b = _system(missing_loop_root)
    claim_b, started_b = _started_claim(workspace_b)
    pre_loop_receipt = facade_b.rebuild(timestamp="2026-08-31T12:00:05+00:00")
    assert pre_loop_receipt["claim_count"] == 60
    pre_loop_row = facade_b.queue(
        now="2026-08-31T12:00:05+00:00",
        query=claim_b,
        limit=100,
    )["items"][0]
    assert pre_loop_row["operational_projection"]["claim_loop_prefix"] is None
    assert pre_loop_row["operational_projection"]["next_state"]["kind"] == (
        "start_processing"
    )
    _ensure(facade_b, claim_b, started_b)
    post_loop_receipt = facade_b.rebuild(
        timestamp="2026-08-31T12:00:06+00:00"
    )
    assert post_loop_receipt["claim_loop_prefix_roster_sha256"] != (
        pre_loop_receipt["claim_loop_prefix_roster_sha256"]
    )

    unexpected_loop_root = tmp_path / "unexpected-loop"
    unexpected_loop_root.mkdir()
    _, workspace_c, _, facade_c = _system(unexpected_loop_root)
    workspace_c.seed(timestamp="2026-08-31T12:00:00+00:00")
    with sqlite3.connect(unexpected_loop_root / "casepath.db") as connection:
        connection.execute(
            """INSERT INTO claim_loop_events(
                session_id,loop_id,sequence,idempotency_key,command_sha256,
                event_sha256,event_json,created_at
            ) VALUES(?,?,?,?,?,?,?,?)""",
            (
                WORKSPACE_CLAIM_LOOP_SESSION_ID,
                "claim-loop.unexpected",
                1,
                "unexpected.foreign.0001",
                "0" * 64,
                "1" * 64,
                "{}",
                "2026-08-31T12:00:01+00:00",
            ),
        )
        connection.commit()
    with pytest.raises(WorkspaceClaimLoopError, match="claim-loop roster"):
        facade_c.rebuild(timestamp="2026-08-31T12:00:05+00:00")

    wrong_binding_root = tmp_path / "wrong-binding"
    wrong_binding_root.mkdir()
    _, workspace_d, _, facade_d = _system(wrong_binding_root)
    workspace_d.seed(timestamp="2026-08-31T12:00:00+00:00")
    claim_d = sorted(workspace_d.corpus.bindings)[0]
    workspace_d.corpus.bindings[claim_d] = {
        **workspace_d.corpus.bindings[claim_d],
        "binding_sha256": "f" * 64,
    }
    with pytest.raises(WorkspaceClaimLoopError, match="workspace import binding"):
        facade_d.rebuild(timestamp="2026-08-31T12:00:05+00:00")


def _kill_after_tool_artifact_child(
    root: str,
    claim_id: str,
    advance_kwargs: dict[str, object],
    marker_path: str,
) -> None:
    _, _, normal, facade = _system(Path(root))
    original_register = normal._register_tool_result

    def register_then_kill(**kwargs: object) -> object:
        receipt = original_register(**kwargs)
        marker = Path(marker_path)
        descriptor = os.open(
            marker,
            os.O_CREAT | os.O_EXCL | os.O_WRONLY,
            0o600,
        )
        try:
            payload = receipt.receipt_sha256.encode("ascii")
            while payload:
                written = os.write(descriptor, payload)
                if written <= 0:  # pragma: no cover - operating-system invariant
                    raise OSError("marker write made no progress")
                payload = payload[written:]
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        directory = os.open(marker.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
        os.kill(os.getpid(), signal.SIGKILL)
        raise AssertionError("SIGKILL returned")  # pragma: no cover

    normal._register_tool_result = register_then_kill  # type: ignore[method-assign]
    facade.advance(claim_id, **advance_kwargs)


def test_workspace_claim_loop_replans_real_claim_and_replays_exactly(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage, workspace, _, facade = _system(tmp_path)
    claim_id, started = _started_claim(workspace)

    view = _ensure(facade, claim_id, started)
    loop = view["loop_state"]
    cycle = loop["six_agent_cycle_receipt"]
    assert tuple(cycle["agent_ids"]) == tuple(AI_AGENT_IDS)
    assert tuple(cycle["deterministic_gate_ids"]) == tuple(DETERMINISTIC_GATE_IDS)
    assert view["outcome"] == "next_action"
    assert loop["phase"] == "awaiting_observation"
    assert loop["selected_action"]["bounded_tool_id"] == facade.adapter.adapter_id
    input_contract = view["input_contract"]
    assert isinstance(input_contract, dict)
    assert input_contract["server_interpretation_only"] is True
    assert tuple(input_contract["registration_body_fields"]) == (
        EVIDENCE_REGISTRATION_FIELDS
    )
    assert view["finding_options"] == []

    action = loop["selected_action"]
    registration_key = "workspace.register.test.0001"
    intent_response = facade.mint_evidence_intent(
        claim_id,
        action_id=action["action_id"],
        expected_revision=loop["revision"],
        idempotency_key=registration_key,
        timestamp="2026-08-31T12:00:01.500000+00:00",
    )
    intent = intent_response["intent"]
    assert (
        facade.mint_evidence_intent(
            claim_id,
            action_id=action["action_id"],
            expected_revision=loop["revision"],
            idempotency_key=registration_key,
            timestamp="2026-08-31T12:00:09+00:00",
        )
        == intent_response
    )
    acquisition_response = facade.acquire_evidence(
        claim_id,
        acquisition_intent_id=intent["intent_id"],
        timestamp="2026-08-31T12:00:01.750000+00:00",
    )
    assert (
        facade.acquire_evidence(
            claim_id,
            acquisition_intent_id=intent["intent_id"],
            timestamp="2026-08-31T12:00:09+00:00",
        )
        == acquisition_response
    )
    acquisition_receipt = acquisition_response["acquisition_receipt"]
    registration_body = {
        "schema": EVIDENCE_REGISTRATION_SCHEMA,
        "action_id": action["action_id"],
        "expected_revision": loop["revision"],
        "idempotency_key": registration_key,
        "acquisition_intent_id": intent["intent_id"],
        "acquisition_receipt_id": acquisition_receipt["acquisition_receipt_id"],
        "content_b64": acquisition_response["content_b64"],
    }
    assert tuple(registration_body) == EVIDENCE_REGISTRATION_FIELDS

    acquired_bytes = base64.b64decode(
        acquisition_response["content_b64"], validate=True
    )
    with pytest.raises(WorkspaceClaimLoopError, match="registered bytes differ"):
        facade.register_evidence(
            claim_id,
            **{
                **registration_body,
                "content_b64": base64.b64encode(acquired_bytes + b"\nmutated").decode(
                    "ascii"
                ),
            },
            timestamp="2026-08-31T12:00:01.800000+00:00",
        )

    with pytest.raises(WorkspaceClaimLoopError, match="registration is stale"):
        facade.register_evidence(
            claim_id,
            **{
                **registration_body,
                "action_id": "action." + "0" * 64,
            },
            timestamp="2026-08-31T12:00:01.900000+00:00",
        )

    stage = facade.register_evidence(
        claim_id,
        **registration_body,
        timestamp="2026-08-31T12:00:02+00:00",
    )
    replay = facade.register_evidence(
        claim_id,
        **registration_body,
        timestamp="2026-08-31T12:00:09+00:00",
    )
    assert replay == stage

    with pytest.raises(WorkspaceClaimLoopError, match="replay differs"):
        facade.register_evidence(
            claim_id,
            **{
                **registration_body,
                "idempotency_key": "workspace.register.conflicting.0001",
            },
            timestamp="2026-08-31T12:00:10+00:00",
        )

    advance_receipt = facade.advance(
        claim_id,
        expected_revision=loop["revision"],
        expected_state_sha256=loop["state_sha256"],
        action_sha256=loop["selected_action"]["action_sha256"],
        stage_receipt_sha256=stage["stage_receipt"]["receipt_sha256"],
        idempotency_key="workspace.advance.test.0001",
    )
    assert (
        advance_receipt["contract"]
        == "casepath.workspace-claim-loop-advance-response/1.0.0"
    )
    assert advance_receipt["claim_loop_response"]["state_sha256"]

    def reject_mutable_state_read(_workspace_state: object) -> None:
        raise AssertionError("completed replay touched mutable current loop state")

    def reject_inner_reentry(**_kwargs: object) -> None:
        raise AssertionError("completed replay re-entered the mutable worker")

    with monkeypatch.context() as replay_guard:
        replay_guard.setattr(facade, "_normal_state", reject_mutable_state_read)
        replay_guard.setattr(facade.claim_loop, "advance", reject_inner_reentry)
        assert (
            facade.advance(
                claim_id,
                expected_revision=loop["revision"],
                expected_state_sha256=loop["state_sha256"],
                action_sha256=loop["selected_action"]["action_sha256"],
                stage_receipt_sha256=stage["stage_receipt"]["receipt_sha256"],
                idempotency_key="workspace.advance.test.0001",
            )
            == advance_receipt
        )
    after = facade.view(claim_id)
    assert after["outcome"] == "next_action"
    assert after["loop_state"]["phase"] == "awaiting_observation"
    assert after["loop_state"]["revision"] == loop["revision"] + 2
    assert after["loop_state"]["selected_action"]["action_sha256"] != (
        loop["selected_action"]["action_sha256"]
    )
    assert after["audit"]["model_calls"] == 0
    assert after["audit"]["provider_calls"] == 0
    assert after["audit"]["cost_usd"] == 0.0
    observation = after["loop_state"]["observations"][0]
    source_ref = observation["source_refs"][0]
    acquired_text = acquired_bytes.decode("utf-8")
    assert observation["value"] == acquired_text
    assert source_ref["source_id"] == acquisition_receipt["source_artifact_id"]
    assert source_ref["source_sha256"] == acquisition_receipt["source_artifact_sha256"]
    assert source_ref["sanitized_excerpt"] == acquired_text
    assert source_ref["text_start"] == acquisition_receipt["text_start"]
    assert source_ref["text_end"] == acquisition_receipt["text_end"]
    assert source_ref["span_sha256"] == acquisition_receipt["content_sha256"]
    assert stage["stage_receipt"]["contract"] == (
        "casepath.workspace-evidence-registration-receipt/1.0.0"
    )

    source_run_id = after["loop_state"]["source_run_id"]
    replayed_initial = _ensure(facade, claim_id, started)
    assert replayed_initial == view
    again = facade.ensure(
        claim_id,
        expected_workspace_revision=int(started["revision"]),
        expected_workspace_state_sha256=str(started["state_sha256"]),
        idempotency_key="workspace.ensure.current." + claim_id,
    )
    assert again["loop_state"]["source_run_id"] == source_run_id
    assert again["loop_state"]["state_sha256"] == after["loop_state"]["state_sha256"]
    with storage.connect() as connection:
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM runs WHERE session_id=? AND claim_id=?",
                (WORKSPACE_CLAIM_LOOP_SESSION_ID, claim_id),
            ).fetchone()[0]
            == 1
        )


def test_workspace_scoped_correction_preview_apply_and_reload_are_exact(
    tmp_path: Path,
) -> None:
    storage, workspace, normal, facade = _system(tmp_path)
    claim_id, started = _started_claim(workspace)
    before = _advance_resolved_once(
        facade,
        claim_id,
        _ensure(facade, claim_id, started),
        suffix="correction.0001",
    )
    options = facade.correction_options(claim_id)
    assert options["revision"] == before["loop_state"]["revision"]
    assert options["state_sha256"] == before["loop_state"]["state_sha256"]
    assert len(options["candidates"]) == 1
    candidate = options["candidates"][0]
    assert candidate["authority_adapter_id"] == facade.correction_adapter.adapter_id
    assert candidate["proposed_semantics"]["fact_state"] == "unknown"
    assert candidate["proposed_semantics"]["normalized_value"] is None
    assert candidate["proposed_semantics"]["evidence_status"] == (
        "provided_insufficient"
    )
    loop_id = before["loop_state"]["loop_id"]
    with storage.connect() as connection:
        event_count_before = connection.execute(
            "SELECT COUNT(*) FROM claim_loop_events WHERE session_id=? AND loop_id=?",
            (WORKSPACE_CLAIM_LOOP_SESSION_ID, loop_id),
        ).fetchone()[0]

    preview_args = {
        "candidate_sha256": candidate["candidate_sha256"],
        "expected_revision": before["loop_state"]["revision"],
        "expected_state_sha256": before["loop_state"]["state_sha256"],
        "idempotency_key": "workspace.correction.preview.0001",
    }
    preview = facade.prepare_correction(claim_id, **preview_args)
    assert facade.prepare_correction(claim_id, **preview_args) == preview
    assert preview["preview"]["before_fact_sha256"] != (
        preview["preview"]["expected_after_fact_sha256"]
    )
    assert preview["preview"]["before_evidence_sha256"] != (
        preview["preview"]["expected_after_evidence_sha256"]
    )
    assert preview["preview"]["unrelated_facts_before_sha256"] == (
        preview["preview"]["unrelated_facts_after_sha256"]
    )
    with storage.connect() as connection:
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM claim_loop_events WHERE session_id=? AND loop_id=?",
                (WORKSPACE_CLAIM_LOOP_SESSION_ID, loop_id),
            ).fetchone()[0]
            == event_count_before
        )

    _, _, _, restarted = _system(tmp_path)
    assert restarted.prepare_correction(claim_id, **preview_args) == preview
    with pytest.raises(WorkspaceClaimLoopError):
        facade.prepare_correction(
            claim_id,
            **{
                **preview_args,
                "candidate_sha256": "0" * 64,
            },
        )

    apply_args = {
        "correction_id": preview["correction_id"],
        "idempotency_key": "workspace.correction.apply.0001",
    }
    applied = facade.apply_workspace_correction(claim_id, **apply_args)
    after = facade.view(claim_id)
    assert after["outcome"] in {"next_action", "decision_ready", "abstain"}
    assert after["outcome"] != "processing"
    if after["outcome"] == "next_action":
        assert after["loop_state"]["selected_action"] is not None
    else:
        assert after["decision_packet"] is not None
    assert after["correction_count"] == 1
    assert after["correction_candidates"] == []
    delta = after["latest_correction"]
    assert delta["correction_id"] == preview["correction_id"]
    assert delta["before_semantics"] == preview["preview"]["before_semantics"]
    assert delta["after_semantics"] == preview["preview"][
        "expected_after_semantics"
    ]
    assert delta["effect"]["fact_state"] == delta["after_semantics"][
        "fact_state"
    ]
    assert delta["effect"]["value"] == delta["after_semantics"]["value"]
    assert delta["effect"]["explanation"] == delta["after_semantics"][
        "explanation"
    ]
    assert delta["effect"]["evidence_status"] == delta["after_semantics"][
        "evidence_status"
    ]
    assert delta["effect"]["normalized_value"] is None
    assert delta["after_semantics"]["normalized_value"] == "unresolved"
    assert delta["before_fact_sha256"] != delta["after_fact_sha256"]
    assert delta["before_evidence_sha256"] != delta["after_evidence_sha256"]
    assert delta["unrelated_facts_before_sha256"] == (
        delta["unrelated_facts_after_sha256"]
    )
    corrected_fact = next(
        value
        for value in after["loop_state"]["facts"]
        if value["fact_id"] == delta["fact_id"]
    )
    corrected_evidence = next(
        value
        for value in after["loop_state"]["checklist"]["items"]
        if value["item_id"] == delta["evidence_item_id"]
    )
    assert corrected_fact["state"] == "unknown"
    assert corrected_fact["normalized_value"] == "unresolved"
    assert corrected_evidence["status"] == "provided_insufficient"
    correction_event = normal.store.events(
        session_id=WORKSPACE_CLAIM_LOOP_SESSION_ID,
        loop_id=loop_id,
    )[-1]
    assert correction_event.event_type == "CORRECTION_APPLIED"
    assert correction_event.command["before_semantics"] == delta[
        "before_semantics"
    ]
    assert correction_event.command["after_semantics"] == delta[
        "after_semantics"
    ]
    cycle = correction_event.command["six_agent_cycle_receipt"]
    assert cycle["cycle_kind"] == "correction"
    assert tuple(cycle["agent_ids"]) == tuple(AI_AGENT_IDS)
    assert tuple(cycle["deterministic_gate_ids"]) == tuple(DETERMINISTIC_GATE_IDS)
    assert cycle["model_calls"] == cycle["provider_calls"] == 0
    assert cycle["credential_access_status"] == "none_due_to_zero_provider_calls"
    assert cycle["credential_access_receipt_sha256s"] == []
    assert cycle["cost_usd"] == 0.0

    # A later legitimate select changes the tail but not the completed apply
    # response bound to the original correction event.
    normal.select_action(
        session_id=WORKSPACE_CLAIM_LOOP_SESSION_ID,
        loop_id=loop_id,
        idempotency_key="workspace.correction.select-later.0001",
    )
    assert facade.apply_workspace_correction(claim_id, **apply_args) == applied
    _, _, _, restarted_after = _system(tmp_path)
    assert restarted_after.apply_workspace_correction(claim_id, **apply_args) == applied
    reloaded = restarted_after.view(claim_id)
    assert reloaded["latest_correction"] == after["latest_correction"]


def test_workspace_correction_adapter_rejects_forged_authority(
    tmp_path: Path,
) -> None:
    _, workspace, normal, facade = _system(tmp_path)
    claim_id, started = _started_claim(workspace)
    after = _advance_resolved_once(
        facade,
        claim_id,
        _ensure(facade, claim_id, started),
        suffix="correction-authority.0001",
    )
    state = normal.state(
        session_id=WORKSPACE_CLAIM_LOOP_SESSION_ID,
        loop_id=after["loop_state"]["loop_id"],
    )
    ledger = state.projection_ledger[-1]
    artifact = normal.store.tool_artifact(ledger.artifact_receipt_sha256)
    assert artifact is not None
    forged = artifact.model_copy(update={"adapter_id": "casepath.tool.forged/1"})
    with pytest.raises(ClaimLoopError, match="correction source"):
        facade.correction_adapter.execute(
            source_artifact=forged,
            state=state,
            timestamp="2026-08-31T12:00:10+00:00",
        )
    ledgerless = state.model_copy(update={"projection_ledger": ()})
    with pytest.raises(ClaimLoopError, match="correction source"):
        facade.correction_adapter.execute(
            source_artifact=artifact,
            state=ledgerless,
            timestamp="2026-08-31T12:00:10+00:00",
        )


def test_workspace_store_reexecutes_configured_correction_authority(
    tmp_path: Path,
) -> None:
    storage, workspace, normal, facade = _system(tmp_path)
    claim_id, started = _started_claim(workspace)
    before = _advance_resolved_once(
        facade,
        claim_id,
        _ensure(facade, claim_id, started),
        suffix="store-correction-authority.0001",
    )
    candidate = facade.correction_options(claim_id)["candidates"][0]
    preview = facade.prepare_correction(
        claim_id,
        candidate_sha256=candidate["candidate_sha256"],
        expected_revision=before["loop_state"]["revision"],
        expected_state_sha256=before["loop_state"]["state_sha256"],
        idempotency_key="workspace.correction.store.preview.0001",
    )
    stored = normal.store.correction(preview["correction_id"])
    assert stored is not None
    correction, source_session_id, source_loop_id = stored
    artifact = normal.store.correction_artifact(
        correction.correction_artifact_receipt_sha256
    )
    assert artifact is not None
    with storage.connect() as connection:
        counts_before = (
            connection.execute(
                "SELECT COUNT(*) FROM claim_loop_correction_artifacts"
            ).fetchone()[0],
            connection.execute(
                "SELECT COUNT(*) FROM claim_loop_corrections"
            ).fetchone()[0],
        )

    forged_adapter_id = "casepath.correction.forged-unconfigured/1.0.0"
    forged_authority_ref = artifact.authority_source_ref.model_copy(
        update={"adapter_id": forged_adapter_id}
    )
    forged_artifact_payload = artifact.model_dump(
        mode="json", exclude={"receipt_sha256"}
    )
    forged_artifact_payload.update(
        {
            "authority_adapter_id": forged_adapter_id,
            "authority_source_ref": forged_authority_ref.model_dump(mode="json"),
            "issuer_id": forged_adapter_id,
        }
    )
    forged_artifact = CorrectionArtifactReceipt.model_validate(
        {
            **forged_artifact_payload,
            "receipt_sha256": digest_value(forged_artifact_payload),
        }
    )
    forged_correction_payload = correction.model_dump(
        mode="json", exclude={"correction_id", "correction_sha256"}
    )
    forged_correction_payload["correction_artifact_receipt_sha256"] = (
        forged_artifact.receipt_sha256
    )
    forged_correction_sha256 = digest_value(forged_correction_payload)
    forged_correction = ScopedCorrection.model_validate(
        {
            **forged_correction_payload,
            "correction_id": f"correction.{forged_correction_sha256}",
            "correction_sha256": forged_correction_sha256,
        }
    )
    with pytest.raises(
        ClaimLoopStoreError,
        match="correction authority adapter is not configured exactly",
    ):
        normal.store.register_correction(
            correction_artifact=forged_artifact,
            correction=forged_correction,
            source_session_id=source_session_id,
            source_loop_id=source_loop_id,
            timestamp=forged_artifact.issued_at,
        )

    class WrongEffectAdapter:
        adapter_id = facade.correction_adapter.adapter_id

        def execute(self, **_: object) -> CorrectionToolResult:
            return CorrectionToolResult(
                effect=artifact.proposed_effect.model_copy(
                    update={"explanation": "forged configured-adapter effect"}
                ),
                issuer_id=self.adapter_id,
                provenance_note=artifact.provenance_note,
            )

    normal.store.correction_adapters[facade.correction_adapter.adapter_id] = (
        WrongEffectAdapter()
    )
    with pytest.raises(
        ClaimLoopStoreError,
        match="proposal differs from its configured adapter",
    ):
        normal.store.register_correction(
            correction_artifact=artifact,
            correction=correction,
            source_session_id=source_session_id,
            source_loop_id=source_loop_id,
            timestamp=artifact.issued_at,
        )
    with storage.connect() as connection:
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM claim_loop_correction_artifacts"
            ).fetchone()[0],
            connection.execute(
                "SELECT COUNT(*) FROM claim_loop_corrections"
            ).fetchone()[0],
        ) == counts_before


def test_workspace_invalid_correction_preview_is_stable_terminal_conflict(
    tmp_path: Path,
) -> None:
    storage, workspace, normal, facade = _system(tmp_path)
    claim_id, started = _started_claim(workspace)
    before = _advance_resolved_once(
        facade,
        claim_id,
        _ensure(facade, claim_id, started),
        suffix="invalid-correction-preview.0001",
    )
    request = {
        "candidate_sha256": "0" * 64,
        "expected_revision": before["loop_state"]["revision"],
        "expected_state_sha256": before["loop_state"]["state_sha256"],
        "idempotency_key": "workspace.correction.preview.invalid.0001",
    }
    failures: list[dict[str, object]] = []
    for _ in range(2):
        with pytest.raises(WorkspaceClaimLoopError) as captured:
            facade.prepare_correction(claim_id, **request)
        assert captured.value.conflict_envelope is not None
        failures.append(captured.value.conflict_envelope)
    assert failures[0] == failures[1]
    assert failures[0]["error_code"] == "REQUEST_PREFIX_SUPERSEDED"
    assert failures[0]["revision"] == before["loop_state"]["revision"]
    assert failures[0]["state_sha256"] == before["loop_state"]["state_sha256"]

    app = FastAPI()
    app.include_router(
        create_claim_loop_router(
            lambda: storage,
            service_getter=lambda: normal,
            workspace_service_getter=lambda: workspace,
            workspace_loop_service_getter=lambda: facade,
        )
    )
    client = TestClient(app)
    body = {key: value for key, value in request.items() if key != "idempotency_key"}
    headers = {"X-CasePath-Idempotency-Key": request["idempotency_key"]}
    first = client.post(
        f"/api/claim-loops/v1/workspace/claims/{claim_id}/loop/corrections/preview",
        json=body,
        headers=headers,
    )
    second = client.post(
        f"/api/claim-loops/v1/workspace/claims/{claim_id}/loop/corrections/preview",
        json=body,
        headers=headers,
    )
    assert first.status_code == second.status_code == 409
    assert first.content == second.content
    assert first.json()["detail"] == failures[0]
    with storage.connect() as connection:
        row = connection.execute(
            """SELECT status,response_json,completed_at
            FROM claim_loop_client_requests
            WHERE session_id=? AND loop_id=? AND idempotency_key=?""",
            (
                WORKSPACE_CLAIM_LOOP_SESSION_ID,
                before["loop_state"]["loop_id"],
                request["idempotency_key"],
            ),
        ).fetchone()
    assert row["status"] == "SUPERSEDED"
    assert row["response_json"] is not None
    assert row["completed_at"] is not None


def test_workspace_source_election_is_unique_under_concurrency(tmp_path: Path) -> None:
    storage, workspace, _, facade = _system(tmp_path)
    claim_id, started = _started_claim(workspace)

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(
            executor.map(
                lambda _: _ensure(facade, claim_id, started),
                range(2),
            )
        )
    assert (
        results[0]["loop_state"]["source_run_id"]
        == results[1]["loop_state"]["source_run_id"]
    )
    assert (
        results[0]["loop_state"]["state_sha256"]
        == results[1]["loop_state"]["state_sha256"]
    )
    with storage.connect() as connection:
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM runs WHERE session_id=? AND claim_id=?",
                (WORKSPACE_CLAIM_LOOP_SESSION_ID, claim_id),
            ).fetchone()[0]
            == 1
        )
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM claim_loop_events WHERE session_id=?",
                (WORKSPACE_CLAIM_LOOP_SESSION_ID,),
            ).fetchone()[0]
            == 2
        )


@pytest.mark.parametrize(
    "coordinate",
    ["session_id", "loop_id", "parent_revision", "action_sha256"],
)
def test_workspace_stage_lookup_rejects_rehashed_coordinate_tamper(
    tmp_path: Path,
    coordinate: str,
) -> None:
    storage, workspace, normal, facade = _system(tmp_path)
    claim_id, started = _started_claim(workspace)
    view = _ensure(facade, claim_id, started)
    loop = view["loop_state"]
    registered = _register_server_evidence(
        facade,
        claim_id,
        view,
        idempotency_key=f"workspace.register.coordinate.{coordinate}.0001",
    )
    staged = registered["stage_receipt"]
    state_before = normal.state(
        session_id=WORKSPACE_CLAIM_LOOP_SESSION_ID,
        loop_id=loop["loop_id"],
    )
    with storage.connect() as connection:
        event_count_before = connection.execute(
            "SELECT COUNT(*) FROM claim_loop_events WHERE session_id=? AND loop_id=?",
            (WORKSPACE_CLAIM_LOOP_SESSION_ID, loop["loop_id"]),
        ).fetchone()[0]
    path = facade.adapter._registration_path(
        session_id=WORKSPACE_CLAIM_LOOP_SESSION_ID,
        loop_id=loop["loop_id"],
        parent_revision=loop["revision"],
        action_sha256=loop["selected_action"]["action_sha256"],
    )
    forged = deepcopy(staged)
    if coordinate == "session_id":
        forged[coordinate] = f"{forged[coordinate]}.tampered"
    elif coordinate == "loop_id":
        forged[coordinate] = f"{forged[coordinate]}.tampered"
    elif coordinate == "parent_revision":
        forged[coordinate] += 1
    else:
        forged[coordinate] = "f" * 64
        forged["action_id"] = "action." + forged[coordinate]
    forged["receipt_sha256"] = digest_value(
        {key: value for key, value in forged.items() if key != "receipt_sha256"}
    )
    path.write_bytes(canonical_json_bytes(forged))

    with pytest.raises(
        WorkspaceEvidenceAuthorityError,
        match="evidence registration lookup differs",
    ):
        facade.adapter.staged(
            session_id=WORKSPACE_CLAIM_LOOP_SESSION_ID,
            loop_id=loop["loop_id"],
            parent_revision=loop["revision"],
            action_sha256=loop["selected_action"]["action_sha256"],
        )
    state_after = normal.state(
        session_id=WORKSPACE_CLAIM_LOOP_SESSION_ID,
        loop_id=loop["loop_id"],
    )
    assert state_after.state_sha256 == state_before.state_sha256
    assert state_after.revision == state_before.revision
    with storage.connect() as connection:
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM claim_loop_events WHERE session_id=? AND loop_id=?",
                (WORKSPACE_CLAIM_LOOP_SESSION_ID, loop["loop_id"]),
            ).fetchone()[0]
            == event_count_before
        )


def test_workspace_dispatch_view_is_processing_and_not_interactive(
    tmp_path: Path,
) -> None:
    storage, workspace, _, facade = _system(tmp_path)
    claim_id, started = _started_claim(workspace)
    view = _ensure(facade, claim_id, started)
    loop = view["loop_state"]
    registered = _register_server_evidence(
        facade,
        claim_id,
        view,
        idempotency_key="workspace.register.dispatch-view.0001",
    )
    stage = registered["registration_response"]
    entered = Event()
    release = Event()
    original_execute = facade.adapter.execute

    def blocked_execute(**kwargs: object) -> object:
        entered.set()
        assert release.wait(timeout=10)
        return original_execute(**kwargs)

    facade.adapter.execute = blocked_execute  # type: ignore[method-assign]
    with ThreadPoolExecutor(max_workers=1) as executor:
        pending = executor.submit(
            facade.advance,
            claim_id,
            expected_revision=loop["revision"],
            expected_state_sha256=loop["state_sha256"],
            action_sha256=loop["selected_action"]["action_sha256"],
            stage_receipt_sha256=stage["stage_receipt"]["receipt_sha256"],
            idempotency_key="workspace.advance.dispatch-view.0001",
        )
        assert entered.wait(timeout=10)
        try:
            during = facade.view(claim_id)
            with storage.connect() as connection:
                event_count_during = connection.execute(
                    "SELECT COUNT(*) FROM claim_loop_events WHERE session_id=? AND loop_id=?",
                    (WORKSPACE_CLAIM_LOOP_SESSION_ID, loop["loop_id"]),
                ).fetchone()[0]
            repeated = facade.view(claim_id)
            _, _, _, restarted_facade = _system(tmp_path)
            restarted = restarted_facade.view(claim_id)
            assert repeated == during
            assert restarted == during
            assert during["loop_state"]["phase"] == "dispatching"
            assert during["loop_state"]["active_dispatch_sha256"] is not None
            assert during["outcome"] == "processing"
            assert during["audit"]["state_sha256"] == during["loop_state"][
                "state_sha256"
            ]
            assert during["audit"]["last_event_sha256"] == during[
                "loop_state"
            ]["last_event_sha256"]
            assert during["audit"]["event_count"] == during["loop_state"][
                "revision"
            ]
            assert during["input_contract"] is None
            assert during["finding_options"] == []
            assert during["stage_receipt"] is None
            with storage.connect() as connection:
                assert (
                    connection.execute(
                        "SELECT COUNT(*) FROM claim_loop_events WHERE session_id=? AND loop_id=?",
                        (WORKSPACE_CLAIM_LOOP_SESSION_ID, loop["loop_id"]),
                    ).fetchone()[0]
                    == event_count_during
                )
        finally:
            release.set()
        response = pending.result(timeout=20)
        assert response["claim_loop_response"]["state_sha256"]
    completed = facade.view(claim_id)
    assert completed["loop_state"]["active_dispatch_sha256"] is None
    assert len(completed["loop_state"]["observations"]) == 1
    assert completed["loop_state"]["action_history"][-1]["outcome"] == "observed"


def test_workspace_sigkill_after_durable_artifact_recovers_without_redispatch(
    tmp_path: Path,
) -> None:
    storage, workspace, normal, facade = _system(tmp_path)
    claim_id, started = _started_claim(workspace)
    view = _ensure(facade, claim_id, started)
    loop = view["loop_state"]
    stage = _register_server_evidence(
        facade,
        claim_id,
        view,
        idempotency_key="workspace.register.sigkill.0001",
    )["registration_response"]
    advance_kwargs: dict[str, object] = {
        "expected_revision": loop["revision"],
        "expected_state_sha256": loop["state_sha256"],
        "action_sha256": loop["selected_action"]["action_sha256"],
        "stage_receipt_sha256": stage["stage_receipt"]["receipt_sha256"],
        "idempotency_key": "workspace.advance.sigkill.0001",
    }
    marker = tmp_path / "artifact-committed.marker"
    process = get_context("fork").Process(
        target=_kill_after_tool_artifact_child,
        args=(str(tmp_path), claim_id, advance_kwargs, str(marker)),
    )
    process.start()
    process.join(timeout=30)
    if process.is_alive():  # pragma: no cover - bounded failure diagnostic
        process.kill()
        process.join(timeout=5)
    assert process.exitcode == -signal.SIGKILL
    assert marker.read_text(encoding="ascii")

    raw_state, raw_events = normal.store.snapshot(
        session_id=WORKSPACE_CLAIM_LOOP_SESSION_ID,
        loop_id=loop["loop_id"],
    )
    assert raw_state.active_dispatch_sha256 is not None
    assert not any(event.event_type == "OBSERVATION_INGESTED" for event in raw_events)
    with storage.connect() as connection:
        assert connection.execute("PRAGMA quick_check").fetchone()[0] == "ok"
        assert connection.execute(
            "SELECT COUNT(*) FROM claim_loop_acquisitions WHERE session_id=? AND loop_id=?",
            (WORKSPACE_CLAIM_LOOP_SESSION_ID, loop["loop_id"]),
        ).fetchone()[0] == 1
        assert connection.execute(
            "SELECT COUNT(*) FROM claim_loop_tool_artifacts WHERE session_id=? AND loop_id=?",
            (WORKSPACE_CLAIM_LOOP_SESSION_ID, loop["loop_id"]),
        ).fetchone()[0] == 1
        assert connection.execute(
            """SELECT status FROM claim_loop_client_requests
            WHERE session_id=? AND loop_id=? AND idempotency_key=?""",
            (
                WORKSPACE_CLAIM_LOOP_SESSION_ID,
                loop["loop_id"],
                advance_kwargs["idempotency_key"],
            ),
        ).fetchone()[0] == "RESERVED"

    _, _, restarted_normal, restarted = _system(tmp_path)

    def forbidden_redispatch(**_: object) -> object:
        raise AssertionError("durable artifact recovery redispatched the adapter")

    restarted.adapter.execute = forbidden_redispatch  # type: ignore[method-assign]
    recovered = restarted.view(claim_id)
    assert recovered["outcome"] in {"next_action", "decision_ready", "abstain"}
    assert recovered["outcome"] != "processing"
    assert recovered["loop_state"]["active_dispatch_sha256"] is None
    assert len(recovered["loop_state"]["observations"]) == 1
    assert len(recovered["loop_state"]["action_history"]) == 1
    assert recovered["loop_state"]["action_history"][0]["outcome"] == "observed"
    assert recovered["audit"]["model_calls"] == 0
    assert recovered["audit"]["provider_calls"] == 0
    assert recovered["audit"]["cost_usd"] == 0.0
    recovered_events = restarted_normal.store.events(
        session_id=WORKSPACE_CLAIM_LOOP_SESSION_ID,
        loop_id=loop["loop_id"],
    )
    result_events = [
        event for event in recovered_events if event.event_type == "OBSERVATION_INGESTED"
    ]
    assert len(result_events) == 1
    cycle = result_events[0].command["six_agent_cycle_receipt"]
    assert tuple(cycle["agent_ids"]) == tuple(AI_AGENT_IDS)
    assert tuple(cycle["deterministic_gate_ids"]) == tuple(DETERMINISTIC_GATE_IDS)
    assert cycle["model_calls"] == cycle["provider_calls"] == 0

    replay = restarted.advance(claim_id, **advance_kwargs)
    second_view = restarted.view(claim_id)
    assert second_view == recovered
    assert replay["claim_loop_response"]["state_sha256"] == recovered[
        "loop_state"
    ]["state_sha256"]
    _, _, _, twice_restarted = _system(tmp_path)
    assert twice_restarted.view(claim_id) == recovered
    with storage.connect() as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM claim_loop_acquisitions WHERE session_id=? AND loop_id=?",
            (WORKSPACE_CLAIM_LOOP_SESSION_ID, loop["loop_id"]),
        ).fetchone()[0] == 1
        assert connection.execute(
            "SELECT COUNT(*) FROM claim_loop_tool_artifacts WHERE session_id=? AND loop_id=?",
            (WORKSPACE_CLAIM_LOOP_SESSION_ID, loop["loop_id"]),
        ).fetchone()[0] == 1
        assert connection.execute(
            """SELECT status FROM claim_loop_client_requests
            WHERE session_id=? AND loop_id=? AND idempotency_key=?""",
            (
                WORKSPACE_CLAIM_LOOP_SESSION_ID,
                loop["loop_id"],
                advance_kwargs["idempotency_key"],
            ),
        ).fetchone()[0] == "COMPLETED"


def test_workspace_facade_precheck_tail_race_terminalizes_stably(
    tmp_path: Path,
) -> None:
    storage, workspace, normal, facade = _system(tmp_path)
    claim_id, started = _started_claim(workspace)
    view = _ensure(facade, claim_id, started)
    loop = view["loop_state"]
    stage = _register_server_evidence(
        facade,
        claim_id,
        view,
        idempotency_key="workspace.register.facade-race.0001",
    )["registration_response"]
    original_advance = normal.advance
    injected = False

    def raced_advance(**kwargs: object) -> object:
        nonlocal injected
        if not injected:
            injected = True
            original_advance(
                **{
                    **kwargs,
                    "idempotency_key": "workspace.advance.facade-race.competitor.0001",
                }
            )
        return original_advance(**kwargs)

    normal.advance = raced_advance  # type: ignore[method-assign]
    advance_kwargs = {
        "expected_revision": loop["revision"],
        "expected_state_sha256": loop["state_sha256"],
        "action_sha256": loop["selected_action"]["action_sha256"],
        "stage_receipt_sha256": stage["stage_receipt"]["receipt_sha256"],
        "idempotency_key": "workspace.advance.facade-race.original.0001",
    }
    with pytest.raises(
        WorkspaceClaimLoopError,
        match="claim loop revision changed before advance admission",
    ):
        facade.advance(claim_id, **advance_kwargs)
    with storage.connect() as connection:
        event_count_after_first = connection.execute(
            "SELECT COUNT(*) FROM claim_loop_events WHERE session_id=? AND loop_id=?",
            (WORKSPACE_CLAIM_LOOP_SESSION_ID, loop["loop_id"]),
        ).fetchone()[0]
    admission = {
        "contract": "casepath.workspace-advance-admission/1.0.0",
        "claim_id": claim_id,
        "loop_id": loop["loop_id"],
        "expected_revision": loop["revision"],
        "expected_state_sha256": loop["state_sha256"],
        "action_id": stage["stage_receipt"]["action_id"],
        "action_sha256": stage["stage_receipt"]["action_sha256"],
        "stage_receipt_sha256": stage["stage_receipt"]["receipt_sha256"],
        "adapter_id": WORKSPACE_EVIDENCE_ADAPTER_ID,
        "adapter_implementation_sha256": facade.adapter.implementation_sha256,
    }
    request_context_sha256 = digest_value(admission)
    request = {
        "expected_revision": loop["revision"],
        "requested_adapter_id": WORKSPACE_EVIDENCE_ADAPTER_ID,
        "request_context_sha256": request_context_sha256,
    }
    request_sha256 = digest_value(request)
    binding = normal.store.client_request(
        session_id=WORKSPACE_CLAIM_LOOP_SESSION_ID,
        loop_id=loop["loop_id"],
        idempotency_key=advance_kwargs["idempotency_key"],
        request_type="advance",
        request_sha256=request_sha256,
    )
    assert binding["status"] == "SUPERSEDED"
    assert binding["response"] is None
    assert binding["failure"]["failure_sha256"] == digest_value(
        {
            key: value
            for key, value in binding["failure"].items()
            if key != "failure_sha256"
        }
    )

    _, _, _, restarted_facade = _system(tmp_path)
    with pytest.raises(
        WorkspaceClaimLoopError,
        match="claim loop revision changed before advance admission",
    ):
        restarted_facade.advance(claim_id, **advance_kwargs)
    with storage.connect() as connection:
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM claim_loop_events WHERE session_id=? AND loop_id=?",
                (WORKSPACE_CLAIM_LOOP_SESSION_ID, loop["loop_id"]),
            ).fetchone()[0]
            == event_count_after_first
        )
    completed = restarted_facade.view(claim_id)
    assert len(completed["loop_state"]["observations"]) == 1
    assert len(completed["loop_state"]["action_history"]) == 1


def test_observed_attempt_bound_is_strict_and_legacy_omission_is_unchanged(
    tmp_path: Path,
) -> None:
    _, workspace, normal, facade = _system(tmp_path)
    claim_id, started = _started_claim(workspace)
    view = _ensure(facade, claim_id, started)
    state = normal.state(
        session_id=WORKSPACE_CLAIM_LOOP_SESSION_ID,
        loop_id=view["loop_state"]["loop_id"],
    )
    assert state.selected_action is not None

    legacy_checklist = deepcopy(state.checklist)
    for item in legacy_checklist["items"]:
        item.pop("max_observed_attempts", None)
    legacy_state = state.model_copy(
        update={"checklist": legacy_checklist, "selected_action": None}
    )
    assert derive_evidence_action_v1(legacy_state) == state.selected_action

    invalid_checklist = deepcopy(state.checklist)
    invalid_checklist["items"][0]["max_observed_attempts"] = True
    invalid_state = state.model_copy(
        update={"checklist": invalid_checklist, "selected_action": None}
    )
    with pytest.raises(
        ClaimLoopError,
        match="observed-attempt bound must be an integer from 1 to 16",
    ):
        derive_evidence_action_v1(invalid_state)


def test_workspace_http_ensure_replays_exact_original_response_after_tail_and_restart(
    tmp_path: Path,
) -> None:
    storage, workspace, normal, facade = _system(tmp_path)
    claim_id, started = _started_claim(workspace)

    def app_for(
        storage_value: Storage,
        workspace_value: ClaimWorkspaceService,
        normal_value: ClaimLoopService,
        facade_value: WorkspaceClaimLoopServiceV1,
    ) -> FastAPI:
        app = FastAPI()
        app.include_router(
            create_claim_loop_router(
                lambda: storage_value,
                service_getter=lambda: normal_value,
                workspace_service_getter=lambda: workspace_value,
                workspace_loop_service_getter=lambda: facade_value,
            )
        )
        return app

    path = f"/api/claim-loops/v1/workspace/claims/{claim_id}/loop"
    body = {
        "expected_workspace_revision": started["revision"],
        "expected_workspace_state_sha256": started["state_sha256"],
    }
    headers = {
        "X-CasePath-Idempotency-Key": "workspace.http.ensure.replay.0001"
    }
    client = TestClient(app_for(storage, workspace, normal, facade))
    first = client.post(path, json=body, headers=headers)
    assert first.status_code == 200
    first_bytes = first.content
    first_view = first.json()

    advanced = _advance_resolved_once(
        facade,
        claim_id,
        first_view,
        suffix="ensure-replay-tail.0001",
    )
    assert advanced["state_sha256"] != first_view["state_sha256"]
    assigned = workspace.assign(
        claim_id,
        owner="Later Handler",
        idempotency_key="workspace.assign.after-ensure.0001",
        expected_revision=int(started["revision"]),
        timestamp="2026-08-31T12:00:06+00:00",
    )
    assert assigned["state"]["revision"] == int(started["revision"]) + 1
    with sqlite3.connect(tmp_path / "casepath.db") as connection:
        loop_event_count_before_replay = connection.execute(
            """SELECT COUNT(*) FROM claim_loop_events
            WHERE session_id=? AND loop_id=?""",
            (
                WORKSPACE_CLAIM_LOOP_SESSION_ID,
                first_view["loop_state"]["loop_id"],
            ),
        ).fetchone()[0]

    replay_after_tail = client.post(path, json=body, headers=headers)
    assert replay_after_tail.status_code == 200
    assert replay_after_tail.content == first_bytes

    storage_fresh, workspace_fresh, normal_fresh, facade_fresh = _system(tmp_path)
    fresh_client = TestClient(
        app_for(storage_fresh, workspace_fresh, normal_fresh, facade_fresh)
    )
    replay_after_restart = fresh_client.post(path, json=body, headers=headers)
    assert replay_after_restart.status_code == 200
    assert replay_after_restart.content == first_bytes
    with sqlite3.connect(tmp_path / "casepath.db") as connection:
        loop_event_count_after_replay = connection.execute(
            """SELECT COUNT(*) FROM claim_loop_events
            WHERE session_id=? AND loop_id=?""",
            (
                WORKSPACE_CLAIM_LOOP_SESSION_ID,
                first_view["loop_state"]["loop_id"],
            ),
        ).fetchone()[0]
    assert loop_event_count_after_replay == loop_event_count_before_replay

    mismatch = fresh_client.post(
        path,
        json={**body, "expected_workspace_state_sha256": "0" * 64},
        headers=headers,
    )
    assert mismatch.status_code == 409


def test_workspace_ensure_crash_after_selection_cannot_migrate_to_later_action(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, workspace, normal, facade = _system(tmp_path)
    claim_id, started = _started_claim(workspace)
    captured: dict[str, object] = {}
    original_complete = normal.store.complete_client_request

    class SimulatedProcessDeath(BaseException):
        pass

    def die_after_selection(**kwargs: object) -> dict[str, object]:
        if kwargs.get("request_type") != "workspace_ensure":
            return original_complete(**kwargs)
        captured.update(kwargs)
        raise SimulatedProcessDeath

    monkeypatch.setattr(normal.store, "complete_client_request", die_after_selection)
    with pytest.raises(SimulatedProcessDeath):
        facade.ensure(
            claim_id,
            expected_workspace_revision=int(started["revision"]),
            expected_workspace_state_sha256=str(started["state_sha256"]),
            idempotency_key="workspace.ensure.crash-after-select.0001",
        )
    monkeypatch.setattr(normal.store, "complete_client_request", original_complete)

    selected_response = captured["response"]
    assert isinstance(selected_response, dict)
    selected_revision = int(selected_response["revision"])
    assert selected_revision >= 1
    advanced = _advance_resolved_once(
        facade,
        claim_id,
        selected_response,
        suffix="ensure-crash-competitor.0001",
    )
    assert advanced["revision"] == selected_revision + 2
    workspace.assign(
        claim_id,
        owner="Concurrent Later Handler",
        idempotency_key="workspace.assign.ensure-crash-competitor.0001",
        expected_revision=int(started["revision"]),
        timestamp="2026-08-31T12:00:07+00:00",
    )

    _, _workspace_fresh, _, facade_fresh = _system(tmp_path)
    recovered = facade_fresh.ensure(
        claim_id,
        expected_workspace_revision=int(started["revision"]),
        expected_workspace_state_sha256=str(started["state_sha256"]),
        idempotency_key="workspace.ensure.crash-after-select.0001",
    )
    assert recovered == selected_response
    assert recovered["revision"] == selected_revision
    assert recovered["state_sha256"] != advanced["state_sha256"]

    with sqlite3.connect(tmp_path / "casepath.db") as connection:
        status = connection.execute(
            """SELECT status FROM claim_loop_client_requests
            WHERE session_id=? AND loop_id=? AND idempotency_key=?""",
            (
                WORKSPACE_CLAIM_LOOP_SESSION_ID,
                recovered["loop_state"]["loop_id"],
                "workspace.ensure.crash-after-select.0001",
            ),
        ).fetchone()
        selection_count = connection.execute(
            """SELECT COUNT(*) FROM claim_loop_events
            WHERE session_id=? AND loop_id=? AND idempotency_key LIKE
                'workspace-select.initial.%'""",
            (
                WORKSPACE_CLAIM_LOOP_SESSION_ID,
                recovered["loop_state"]["loop_id"],
            ),
        ).fetchone()[0]
    assert status == ("COMPLETED",)
    assert selection_count == 1


def test_workspace_http_stage_replay_and_restart_use_one_journal(
    tmp_path: Path,
) -> None:
    storage, workspace, normal, facade = _system(tmp_path)
    claim_id, started = _started_claim(workspace)
    app = FastAPI()
    app.include_router(
        create_claim_loop_router(
            lambda: storage,
            service_getter=lambda: normal,
            workspace_service_getter=lambda: workspace,
            workspace_loop_service_getter=lambda: facade,
        )
    )
    client = TestClient(app)
    loop_response = client.post(
        f"/api/claim-loops/v1/workspace/claims/{claim_id}/loop",
        json={
            "expected_workspace_revision": started["revision"],
            "expected_workspace_state_sha256": started["state_sha256"],
        },
        headers={"X-CasePath-Idempotency-Key": "workspace.http.loop.0001"},
    )
    assert loop_response.status_code == 200
    view = loop_response.json()
    loop = view["loop_state"]
    first_exchange = _http_register_server_evidence(
        client,
        claim_id,
        view,
        idempotency_key="workspace.http.register.0001",
    )
    body = first_exchange["registration_body"]
    headers = first_exchange["registration_headers"]
    first = first_exchange["registration_response"]
    intent_replay = client.post(
        f"/api/claim-loops/v1/workspace/claims/{claim_id}/loop/evidence/intents",
        json=first_exchange["intent_body"],
    )
    assert intent_replay.status_code == 200
    assert intent_replay.content == first_exchange["intent_response"].content
    acquisition_replay = client.post(first_exchange["acquire_path"])
    assert acquisition_replay.status_code == 200
    assert acquisition_replay.content == first_exchange["acquisition_response"].content
    second = client.post(
        f"/api/claim-loops/v1/workspace/claims/{claim_id}/loop/evidence",
        json=body,
        headers=headers,
    )
    assert first.status_code == second.status_code == 200
    assert first.content == second.content

    _, _workspace_after_stage, _, facade_after_stage = _system(tmp_path)
    restarted_stage = facade_after_stage.view(claim_id)
    assert (
        restarted_stage["stage_receipt"]["receipt_sha256"]
        == first.json()["stage_receipt"]["receipt_sha256"]
    )
    assert restarted_stage["loop_state"]["state_sha256"] == loop["state_sha256"]

    advance_body = {
        "expected_revision": loop["revision"],
        "expected_state_sha256": loop["state_sha256"],
        "action_sha256": loop["selected_action"]["action_sha256"],
        "stage_receipt_sha256": first.json()["stage_receipt"]["receipt_sha256"],
    }
    advance_headers = {
        "X-CasePath-Idempotency-Key": "workspace.http.advance.0001"
    }
    first_advance = client.post(
        f"/api/claim-loops/v1/workspace/claims/{claim_id}/loop/advance",
        json=advance_body,
        headers=advance_headers,
    )
    replay_advance = client.post(
        f"/api/claim-loops/v1/workspace/claims/{claim_id}/loop/advance",
        json=advance_body,
        headers=advance_headers,
    )
    assert first_advance.status_code == replay_advance.status_code == 200
    assert first_advance.content == replay_advance.content
    assert (
        first_advance.json()["contract"]
        == "casepath.workspace-claim-loop-advance-response/1.0.0"
    )
    advanced_view = client.get(
        f"/api/claim-loops/v1/workspace/claims/{claim_id}/loop"
    ).json()
    assert advanced_view["loop_state"]["state_sha256"] == (
        first_advance.json()["claim_loop_response"]["state_sha256"]
    )

    next_loop = advanced_view["loop_state"]
    next_exchange = _http_register_server_evidence(
        client,
        claim_id,
        advanced_view,
        idempotency_key="workspace.http.register.0002",
    )
    next_stage = next_exchange["registration_response"]
    next_advance = client.post(
        f"/api/claim-loops/v1/workspace/claims/{claim_id}/loop/advance",
        json={
            "expected_revision": next_loop["revision"],
            "expected_state_sha256": next_loop["state_sha256"],
            "action_sha256": next_loop["selected_action"]["action_sha256"],
            "stage_receipt_sha256": next_stage.json()["stage_receipt"][
                "receipt_sha256"
            ],
        },
        headers={"X-CasePath-Idempotency-Key": "workspace.http.advance.0002"},
    )
    assert next_advance.status_code == 200
    after_inconclusive = client.get(
        f"/api/claim-loops/v1/workspace/claims/{claim_id}/loop"
    ).json()
    inconclusive_observation = after_inconclusive["loop_state"]["observations"][-1]
    assert inconclusive_observation["fact_state"] == "unknown"
    assert inconclusive_observation["normalized_value"] is None
    assert inconclusive_observation["evidence_status"] == "provided_insufficient"
    assert after_inconclusive["outcome"] == "next_action"
    assert after_inconclusive["loop_state"]["selected_action"]["action_kind"] == (
        "validate"
    )
    assert (
        after_inconclusive["loop_state"]["selected_action"]["evidence_item_id"]
        == next_loop["selected_action"]["evidence_item_id"]
    )
    validation_loop = after_inconclusive["loop_state"]
    validation_exchange = _http_register_server_evidence(
        client,
        claim_id,
        after_inconclusive,
        idempotency_key="workspace.http.register.0003",
    )
    validation_stage = validation_exchange["registration_response"]
    validation_advance = client.post(
        f"/api/claim-loops/v1/workspace/claims/{claim_id}/loop/advance",
        json={
            "expected_revision": validation_loop["revision"],
            "expected_state_sha256": validation_loop["state_sha256"],
            "action_sha256": validation_loop["selected_action"]["action_sha256"],
            "stage_receipt_sha256": validation_stage.json()["stage_receipt"][
                "receipt_sha256"
            ],
        },
        headers={"X-CasePath-Idempotency-Key": "workspace.http.advance.0003"},
    )
    assert validation_advance.status_code == 200
    terminal = client.get(
        f"/api/claim-loops/v1/workspace/claims/{claim_id}/loop"
    ).json()
    assert terminal["outcome"] == "abstain"
    assert terminal["loop_state"]["phase"] == "abstained"
    assert terminal["loop_state"]["terminal_mode"] == "abstain"
    assert terminal["loop_state"]["selected_action"] is None
    assert terminal["loop_state"]["abstain_reason"] == (
        "mandatory evidence is unresolved and no bounded action remains"
    )
    assert terminal["decision_packet"]["source_state_sha256"] == terminal[
        "loop_state"
    ]["state_sha256"]
    specialist_history = [
        value
        for value in terminal["loop_state"]["action_history"]
        if value["action"]["evidence_item_id"]
        == next_loop["selected_action"]["evidence_item_id"]
    ]
    assert [value["action"]["action_kind"] for value in specialist_history] == [
        "acquire",
        "validate",
    ]
    assert [value["outcome"] for value in specialist_history] == [
        "observed",
        "observed",
    ]
    late_stage_replay = client.post(
        f"/api/claim-loops/v1/workspace/claims/{claim_id}/loop/evidence",
        json=body,
        headers=headers,
    )
    assert late_stage_replay.status_code == 200
    assert late_stage_replay.content == first.content
    late_replay = client.post(
        f"/api/claim-loops/v1/workspace/claims/{claim_id}/loop/advance",
        json=advance_body,
        headers=advance_headers,
    )
    assert late_replay.status_code == 200
    assert late_replay.content == first_advance.content

    stale_fresh_key = "workspace.http.advance.stale.0009"
    stale = client.post(
        f"/api/claim-loops/v1/workspace/claims/{claim_id}/loop/advance",
        json=advance_body,
        headers={"X-CasePath-Idempotency-Key": stale_fresh_key},
    )
    assert stale.status_code == 409
    with storage.connect() as connection:
        assert (
            connection.execute(
                """SELECT COUNT(*) FROM claim_loop_client_requests
                WHERE session_id=? AND loop_id=? AND idempotency_key=?""",
                (
                    WORKSPACE_CLAIM_LOOP_SESSION_ID,
                    loop["loop_id"],
                    stale_fresh_key,
                ),
            ).fetchone()[0]
            == 0
        )

    _, _workspace_after, _, facade_after = _system(tmp_path)
    restarted = facade_after.view(claim_id)
    current = client.get(
        f"/api/claim-loops/v1/workspace/claims/{claim_id}/loop"
    ).json()
    assert restarted["loop_state"]["state_sha256"] == current["loop_state"][
        "state_sha256"
    ]
    fresh_app = FastAPI()
    fresh_app.include_router(
        create_claim_loop_router(
            lambda: facade_after.claim_loop.storage,
            service_getter=lambda: facade_after.claim_loop,
            workspace_service_getter=lambda: facade_after.workspace,
            workspace_loop_service_getter=lambda: facade_after,
        )
    )
    restarted_client = TestClient(fresh_app)
    restarted_stage_replay = restarted_client.post(
        f"/api/claim-loops/v1/workspace/claims/{claim_id}/loop/evidence",
        json=body,
        headers=headers,
    )
    assert restarted_stage_replay.status_code == 200
    assert restarted_stage_replay.content == first.content
    restarted_replay = restarted_client.post(
        f"/api/claim-loops/v1/workspace/claims/{claim_id}/loop/advance",
        json=advance_body,
        headers=advance_headers,
    )
    assert restarted_replay.status_code == 200
    assert restarted_replay.content == first_advance.content

    before_tail = (
        sqlite3.connect(tmp_path / "casepath.db")
        .execute(
            "SELECT COUNT(*) FROM claim_loop_events WHERE session_id=?",
            (WORKSPACE_CLAIM_LOOP_SESSION_ID,),
        )
        .fetchone()[0]
    )
    bad = client.post(
        f"/api/claim-loops/v1/workspace/claims/{claim_id}/loop/evidence",
        json={**body, "finding": "client_authored_expected_action"},
        headers=headers,
    )
    assert bad.status_code == 422
    assert (
        sqlite3.connect(tmp_path / "casepath.db")
        .execute(
            "SELECT COUNT(*) FROM claim_loop_events WHERE session_id=?",
            (WORKSPACE_CLAIM_LOOP_SESSION_ID,),
        )
        .fetchone()[0]
        == before_tail
    )
