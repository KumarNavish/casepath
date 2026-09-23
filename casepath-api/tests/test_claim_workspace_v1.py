from __future__ import annotations

from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import math
from pathlib import Path
import shutil
import sqlite3
import time
import threading

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from casepath_api.claim_loop_router import create_claim_loop_router
from casepath_api.claim_workspace_v1 import (
    ClaimWorkspaceError,
    ClaimWorkspaceService,
    _row,
    _sort_key,
)
from casepath_api.claim_workspace_intake_v1 import (
    INTAKE_TERM_CATALOG,
    compile_intake_assessment,
    validate_recorded_intake_assessment,
)
from casepath_api.storage import ReservedSessionResetError, Storage
from casepath_api.workspace_corpus import (
    PublicCorpus,
    WorkspaceCorpusError,
    default_public_corpus_root,
    digest_value,
)


FIXED_TIME = "2026-08-31T12:00:00+00:00"
FROZEN_INTAKE_CATALOG_SHA256_V1_1 = (
    "d550af3b4361098e1717f54422f219753b24fee854f8639d4f7bfa4de460b6d1"
)
FROZEN_INTAKE_ASSESSMENT_ROSTER_SHA256_V1_1 = (
    "4cf1b7f7e506a3141086a877fefbfbfdbacd88887a8ca9f0241bf8970c684a71"
)


def canonical(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


@pytest.fixture(scope="session")
def corpus() -> PublicCorpus:
    return PublicCorpus(default_public_corpus_root())


@pytest.fixture(scope="session")
def seeded_database(tmp_path_factory: pytest.TempPathFactory, corpus: PublicCorpus) -> Path:
    path = tmp_path_factory.mktemp("claim-workspace-template") / "casepath.db"
    receipt = ClaimWorkspaceService(Storage(str(path)), corpus).seed(
        timestamp="2026-08-31T00:00:00+00:00"
    )
    assert receipt["claim_count"] == 60
    assert receipt["new_import_count"] == 60
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    return path


@pytest.fixture()
def service(
    tmp_path: Path,
    seeded_database: Path,
    corpus: PublicCorpus,
) -> ClaimWorkspaceService:
    path = tmp_path / "casepath.db"
    shutil.copy2(seeded_database, path)
    return ClaimWorkspaceService(Storage(str(path)), corpus)


def test_public_corpus_is_closed_and_outcome_blind(corpus: PublicCorpus) -> None:
    assert corpus.root.name == "synthetic-dev-60"
    assert corpus.manifest["corpus_id"] == "synthetic-dev-60"
    assert corpus.identity["claim_count"] == 60
    assert corpus.identity["file_count"] == 258
    assert corpus.manifest["manifest_sha256"] == (
        "0e4854731bffdd618022fc12b40b82b75fef14c3c1ad5f91611aa1144ef5ec2e"
    )
    assert corpus.manifest["contains_sealed_targets"] is False
    assert corpus.manifest["contains_expected_outputs"] is False
    assert corpus.manifest["license"]["path"] == "LICENSE-DATA"
    forbidden = {
        "domain",
        "family_id",
        "split",
        "gold",
        "target",
        "oracle",
        "expected_output",
        "hidden_commitment",
    }
    for binding in corpus.bindings.values():
        assert forbidden.isdisjoint(binding)
        assert binding["static_template_sha256"] == corpus.identity[
            "static_template_sha256"
        ]


def test_intake_compiler_is_source_bound_complete_and_outcome_blind(
    corpus: PublicCorpus,
) -> None:
    import casepath_api.claim_workspace_intake_v1 as compiler

    assessments = [
        compiler._compile_intake_assessment_v1_1(corpus, claim_id)
        for claim_id in sorted(corpus.bindings)
    ]
    assert len(assessments) == 60
    assert digest_value(
        [
            {
                "claim_id": row["claim_id"],
                "assessment_sha256": row["assessment_sha256"],
            }
            for row in assessments
        ]
    ) == FROZEN_INTAKE_ASSESSMENT_ROSTER_SHA256_V1_1
    assert (
        digest_value(compiler._catalog_material_v1_1())
        == FROZEN_INTAKE_CATALOG_SHA256_V1_1
    )
    assert {row["claim_type"] for row in assessments} == {
        "defect_mold_heating",
        "lease_termination_dispute",
        "rent_increase_dispute",
    }
    assert all(
        len([score for score in row["domain_scores"] if score["score"] > 0]) == 1
        for row in assessments
    )
    forbidden = {
        "gold",
        "target",
        "oracle",
        "expected_action",
        "expected_output",
        "selected_action",
        "hidden",
        "family_id",
        "split",
    }
    for assessment in assessments:
        encoded = canonical(assessment).decode("utf-8").casefold()
        assert all(f'"{name}"' not in encoded for name in forbidden)
        assert assessment["binding_sha256"] == corpus.binding(
            assessment["claim_id"]
        )["binding_sha256"]
        assert assessment["current_node"]["terminal"] is False
        assert assessment["outgoing_branches"]
        assert assessment["activity"] == {
            "model_calls": 0,
            "provider_calls": 0,
            "credential_reads": 0,
            "cost_usd": 0,
        }


def test_intake_compiler_is_invariant_to_catalog_order(
    corpus: PublicCorpus,
) -> None:
    import casepath_api.claim_workspace_intake_v1 as compiler

    claim_id = sorted(corpus.bindings)[0]
    expected = compile_intake_assessment(corpus, claim_id)
    reversed_catalog = {
        key: tuple(reversed(INTAKE_TERM_CATALOG[key]))
        for key in reversed(tuple(INTAKE_TERM_CATALOG))
    }
    subject = corpus.claim(claim_id)["customer_message"]["subject"].casefold()
    assert compiler._score_subject_v1_1(subject, reversed_catalog) == expected[
        "domain_scores"
    ]
    assert compiler._catalog_material_v1_1(reversed_catalog) == json.loads(
        canonical(compiler._catalog_material_v1_1())
    )


def test_recorded_v1_1_assessment_ignores_successor_default_aliases(
    corpus: PublicCorpus, monkeypatch: pytest.MonkeyPatch
) -> None:
    import casepath_api.claim_workspace_intake_v1 as compiler

    claim_id = sorted(corpus.bindings)[0]
    recorded = compiler._compile_intake_assessment_v1_1(corpus, claim_id)
    monkeypatch.setattr(compiler, "INTAKE_TERM_CATALOG", {"future": ("future",)})
    monkeypatch.setattr(
        compiler,
        "INTAKE_ASSESSMENT_CONTRACT",
        "casepath.deterministic-intake-assessment/1.2.0",
    )
    monkeypatch.setattr(
        compiler,
        "INTAKE_COMPILER_ID",
        "casepath.observable-message-policy-compiler/1.2.0",
    )
    assert validate_recorded_intake_assessment(
        recorded, corpus=corpus, claim_id=claim_id
    ) == recorded


def test_journal_replay_dispatches_recorded_compiler_not_latest_default(
    service: ClaimWorkspaceService, monkeypatch: pytest.MonkeyPatch
) -> None:
    import casepath_api.claim_workspace_v1 as workspace

    claim_id = service.queue(now=FIXED_TIME)["items"][0]["claim_id"]
    accepted_response = service.start(
        claim_id,
        idempotency_key="recorded-compiler-start-0001",
        expected_revision=1,
        timestamp="2026-08-31T12:01:00+00:00",
    )
    accepted = accepted_response["state"]

    def future_default(*_args: object, **_kwargs: object) -> dict[str, object]:
        raise AssertionError("latest compiler must not be called during replay")

    monkeypatch.setattr(workspace, "compile_intake_assessment", future_default)
    assert service.store.recover(claim_id) == accepted
    replay = service.start(
        claim_id,
        idempotency_key="recorded-compiler-start-0001",
        expected_revision=1,
        timestamp="2026-08-31T20:00:00+00:00",
    )
    assert canonical(replay) == canonical(accepted_response)
    with pytest.raises(ClaimWorkspaceError, match="different input"):
        service.start(
            claim_id,
            idempotency_key="recorded-compiler-start-0001",
            expected_revision=2,
        )


def test_v2_golden_start_event_and_state_are_exact(
    service: ClaimWorkspaceService,
) -> None:
    claim_id = "clm_0b431bbf8391ce3e"
    response = service.start(
        claim_id,
        idempotency_key="golden-v1-1-start-0001",
        expected_revision=1,
        timestamp="2026-08-31T12:01:00+00:00",
    )
    assert response["state"]["intake_assessment"]["compiler_id"] == (
        "casepath.claim-workspace-assessment-v2/1.0.0"
    )
    assert response["state"]["intake_assessment"]["assessment_sha256"] == (
        compile_intake_assessment(service.corpus, claim_id)["assessment_sha256"]
    )
    assert response["event_sha256"] == response["state"]["last_event_sha256"]
    assert service.store.recover(claim_id) == response["state"]


def test_corpus_rechecks_claim_policy_and_manifest_after_admission(
    tmp_path: Path,
    corpus: PublicCorpus,
    writable_corpus_copy,
) -> None:
    copied_root = writable_corpus_copy(corpus.root, tmp_path / "corpus")
    admitted = PublicCorpus(copied_root)
    claim_id = sorted(admitted.bindings)[0]

    claim_path = copied_root / admitted.binding(claim_id)["claim"]["path"]
    claim_raw = claim_path.read_bytes()
    claim_path.write_bytes(bytes([claim_raw[0] ^ 1]) + claim_raw[1:])
    with pytest.raises(WorkspaceCorpusError, match="drifted"):
        admitted.claim(claim_id)
    claim_path.write_bytes(claim_raw)

    policy_path = copied_root / admitted.static_policy_file_identity["path"]
    policy_raw = policy_path.read_bytes()
    assert b"Preserve" in policy_raw
    policy_path.write_bytes(policy_raw.replace(b"Preserve", b"preserve", 1))
    with pytest.raises(WorkspaceCorpusError, match="drifted"):
        admitted.static_policy()
    policy_path.write_bytes(policy_raw)

    drift_database = tmp_path / "manifest-drift.db"
    admitted_service = ClaimWorkspaceService(Storage(str(drift_database)), admitted)
    admitted_service.seed(timestamp="2026-08-31T00:00:00+00:00")
    with sqlite3.connect(drift_database) as connection:
        before_events = connection.execute(
            "SELECT COUNT(*) FROM claim_loop_events WHERE session_id=?",
            ("casepath-workspace-local",),
        ).fetchone()[0]

    manifest_path = copied_root / "manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    manifest["corpus_version"] = "99.0.0"
    manifest["manifest_sha256"] = digest_value(
        {key: item for key, item in manifest.items() if key != "manifest_sha256"}
    )
    manifest_path.write_bytes(canonical(manifest))
    with pytest.raises(WorkspaceCorpusError, match="drifted"):
        admitted.binding(claim_id)
    with pytest.raises(WorkspaceCorpusError, match="drifted"):
        _ = admitted.identity
    with pytest.raises(WorkspaceCorpusError, match="drifted"):
        admitted_service.seed(timestamp="2026-08-31T00:01:00+00:00")
    with pytest.raises(ClaimWorkspaceError, match="binding"):
        admitted_service.store.recover(claim_id)
    with sqlite3.connect(drift_database) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM claim_loop_events WHERE session_id=?",
            ("casepath-workspace-local",),
        ).fetchone()[0] == before_events
    with pytest.raises(WorkspaceCorpusError, match="manifest is invalid"):
        PublicCorpus(copied_root)


def test_seed_is_exactly_once_and_byte_stable(service: ClaimWorkspaceService) -> None:
    replay = service.seed(timestamp="2026-08-31T08:00:00+00:00")
    assert replay["claim_count"] == 60
    assert replay["new_import_count"] == 0
    assert replay["replayed_import_count"] == 60
    assert len(service.states()) == 60
    assert len({row["claim_id"] for row in service.states()}) == 60


def test_cursor_pages_are_complete_disjoint_and_snapshot_bound(
    service: ClaimWorkspaceService,
) -> None:
    seen: list[str] = []
    cursor = None
    as_of = FIXED_TIME
    while True:
        page = service.queue(now=as_of if cursor is None else None, cursor=cursor, limit=17)
        assert page["generated_at"] == as_of
        seen.extend(row["claim_id"] for row in page["items"])
        cursor = page["next_cursor"]
        if cursor is None:
            break
    assert len(seen) == 60
    assert len(set(seen)) == 60

    first = service.queue(now=as_of, limit=9)
    claim_id = first["items"][0]["claim_id"]
    service.assign(
        claim_id,
        owner="Handler A",
        idempotency_key="cursor-drift-owner-0001",
        expected_revision=1,
        timestamp="2026-08-31T12:01:00+00:00",
    )
    with pytest.raises(ClaimWorkspaceError, match="stale"):
        service.queue(cursor=first["next_cursor"], limit=9)


def test_filters_and_sorts_are_exact(service: ClaimWorkspaceService) -> None:
    initial = service.queue(now=FIXED_TIME, limit=100)
    claim_id = initial["items"][0]["claim_id"]
    service.assign(
        claim_id,
        owner="Ada",
        idempotency_key="filter-owner-0001",
        expected_revision=1,
        timestamp="2026-08-31T12:01:00+00:00",
    )
    service.start(
        claim_id,
        idempotency_key="filter-start-0001",
        expected_revision=2,
        timestamp="2026-08-31T12:02:00+00:00",
    )
    assert service.queue(now=FIXED_TIME, owner="Ada")["total_count"] == 1
    assert service.queue(now=FIXED_TIME, state="in_review")["total_count"] == 1
    assert service.queue(now=FIXED_TIME, readiness="blocked")["total_count"] == 1
    assert service.queue(now=FIXED_TIME, claim_type="unclassified_intake")[
        "total_count"
    ] == 59
    classified = service.store.recover(claim_id)
    assert classified["claim_type"] != "unclassified_intake"
    assert classified["intake_assessment"]["claim_id"] == claim_id
    assert classified["next_safe_action"] == classified["intake_assessment"][
        "current_node"
    ]["label"]
    assert service.queue(now=FIXED_TIME, pending_evidence="unknown")[
        "total_count"
    ] == 60
    assert service.queue(now=FIXED_TIME, failure=False)["total_count"] == 60
    assert service.queue(now=FIXED_TIME, query=claim_id)["total_count"] == 1
    for mode in (
        "priority",
        "urgency",
        "oldest_waiting",
        "nearest_deadline",
        "most_decision_ready",
        "latest_update",
    ):
        response = service.queue(now=FIXED_TIME, sort=mode, limit=100)
        assert response["items"]


def test_detail_and_artifact_bytes_match_binding(
    service: ClaimWorkspaceService,
    corpus: PublicCorpus,
) -> None:
    claim_id = sorted(corpus.bindings)[0]
    detail = service.detail(claim_id)
    claim = corpus.claim(claim_id)
    assert detail["message"]["body"] == claim["customer_message"]["body"]
    assert detail["message"]["subject"] == claim["customer_message"]["subject"]
    assert detail["artifacts"]
    for artifact in detail["artifacts"]:
        raw, row = corpus.artifact(claim_id, artifact["artifact_id"])
        assert hashlib.sha256(raw).hexdigest() == row["sha256"] == artifact["sha256"]
        assert len(raw) == row["size_bytes"] == artifact["size_bytes"]


def test_mutation_replay_is_byte_identical_after_later_tail(
    service: ClaimWorkspaceService,
) -> None:
    claim_id = service.queue(now=FIXED_TIME)["items"][0]["claim_id"]
    first = service.assign(
        claim_id,
        owner="Grace",
        idempotency_key="byte-replay-owner-0001",
        expected_revision=1,
        timestamp="2026-08-31T12:01:00+00:00",
    )
    service.start(
        claim_id,
        idempotency_key="byte-replay-start-0001",
        expected_revision=2,
        timestamp="2026-08-31T12:02:00+00:00",
    )
    replay = service.assign(
        claim_id,
        owner="Grace",
        idempotency_key="byte-replay-owner-0001",
        expected_revision=1,
        timestamp="2026-08-31T20:00:00+00:00",
    )
    assert canonical(first) == canonical(replay)
    with pytest.raises(ClaimWorkspaceError, match="different input"):
        service.assign(
            claim_id,
            owner="Different",
            idempotency_key="byte-replay-owner-0001",
            expected_revision=1,
        )
    with pytest.raises(ClaimWorkspaceError, match="different input"):
        service.assign(
            claim_id,
            owner="Grace",
            idempotency_key="byte-replay-owner-0001",
            expected_revision=2,
        )


def test_forged_intake_assessment_fails_before_journal_append(
    service: ClaimWorkspaceService,
) -> None:
    claim_id = service.queue(now=FIXED_TIME)["items"][0]["claim_id"]
    binding = service.corpus.binding(claim_id)
    assessment = compile_intake_assessment(service.corpus, claim_id)
    assessment["current_node"]["label"] = "Finalize this claim"
    assessment["assessment_sha256"] = digest_value(
        {key: item for key, item in assessment.items() if key != "assessment_sha256"}
    )
    with pytest.raises(ClaimWorkspaceError, match="source-bound"):
        service.store.append(
            claim_id=claim_id,
            event_type="WORKSPACE_PROCESSING_STARTED",
            idempotency_key="forged-intake-assessment-0001",
            command={
                "expected_binding_sha256": binding["binding_sha256"],
                "intake_assessment": assessment,
                "request_expected_revision": 1,
            },
            timestamp=FIXED_TIME,
            expected_revision=1,
        )
    assert service.store.recover(claim_id)["revision"] == 1


def test_stale_revision_and_cross_route_key_fail_closed(
    service: ClaimWorkspaceService,
) -> None:
    claim_id = service.queue(now=FIXED_TIME)["items"][0]["claim_id"]
    with pytest.raises(ClaimWorkspaceError, match="stale"):
        service.assign(
            claim_id,
            owner="Handler",
            idempotency_key="stale-owner-0001",
            expected_revision=99,
        )
    service.assign(
        claim_id,
        owner="Handler",
        idempotency_key="cross-route-key-0001",
        expected_revision=1,
    )
    with pytest.raises(ClaimWorkspaceError, match="different"):
        service.start(
            claim_id,
            idempotency_key="cross-route-key-0001",
            expected_revision=2,
        )


@pytest.mark.parametrize("revision", (None, True, False, -1))
def test_every_workspace_mutation_requires_an_exact_integer_revision(
    service: ClaimWorkspaceService, revision: object
) -> None:
    claim_id = service.queue(now=FIXED_TIME)["items"][0]["claim_id"]
    with pytest.raises(ClaimWorkspaceError, match="expected revision"):
        service.assign(
            claim_id,
            owner="Unsafe",
            idempotency_key=f"invalid-revision-{revision!s}-0001",
            expected_revision=revision,  # type: ignore[arg-type]
        )
    assert service.store.recover(claim_id)["revision"] == 1


def test_concurrent_distinct_assignments_have_one_cas_winner(
    service: ClaimWorkspaceService,
) -> None:
    claim_id = service.queue(now=FIXED_TIME)["items"][0]["claim_id"]
    barrier = threading.Barrier(2)

    def assign(owner: str) -> tuple[str, str]:
        barrier.wait()
        try:
            response = service.assign(
                claim_id,
                owner=owner,
                idempotency_key=f"concurrent-{owner.lower()}-0001",
                expected_revision=1,
            )
            return "accepted", response["state"]["owner"]
        except ClaimWorkspaceError as exc:
            return "rejected", str(exc)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(assign, ("Alice", "Bob")))
    assert [status for status, _ in results].count("accepted") == 1
    assert [status for status, _ in results].count("rejected") == 1
    assert service.store.recover(claim_id)["revision"] == 2


def test_rebuild_is_a_pure_journal_projection(service: ClaimWorkspaceService) -> None:
    before = service.rebuild(timestamp=FIXED_TIME)
    after = service.rebuild(timestamp=FIXED_TIME)
    assert canonical(before) == canonical(after)
    assert before["claim_count"] == 60
    assert before["authority"] == "claim_loop_events"


def test_corrupt_journal_never_becomes_queue_authority(
    service: ClaimWorkspaceService,
) -> None:
    claim_id = service.queue(now=FIXED_TIME)["items"][0]["claim_id"]
    with service.store.journal.connect() as connection:
        connection.execute(
            """UPDATE claim_loop_events SET event_json='{}'
            WHERE session_id=? AND loop_id=? AND sequence=1""",
            ("casepath-workspace-local", "workspace." + claim_id),
        )
    with pytest.raises(ClaimWorkspaceError, match="chain"):
        service.store.recover(claim_id)
    with pytest.raises(ClaimWorkspaceError):
        service.rebuild(timestamp=FIXED_TIME)


def test_journal_row_cannot_move_between_loop_partitions(
    service: ClaimWorkspaceService,
) -> None:
    claim_id = service.queue(now=FIXED_TIME)["items"][0]["claim_id"]
    with service.store.journal.connect() as connection:
        connection.execute(
            """UPDATE claim_loop_events SET loop_id=?
            WHERE session_id=? AND loop_id=? AND sequence=1""",
            (
                "workspace.fake-claim",
                "casepath-workspace-local",
                "workspace." + claim_id,
            ),
        )
    with pytest.raises(ClaimWorkspaceError, match="chain"):
        service.store.recover("fake-claim")


def test_import_cannot_bind_another_claim_or_forge_corpus_identity(
    service: ClaimWorkspaceService, tmp_path: Path,
) -> None:
    real_claim = sorted(service.corpus.bindings)[0]
    binding = service.corpus.binding(real_claim)
    forged_identity = dict(service.corpus.identity)
    forged_identity["claim_count"] = 59
    with pytest.raises(ClaimWorkspaceError, match="binding"):
        service.store.append(
            claim_id="fake-claim",
            event_type="WORKSPACE_CLAIM_IMPORTED",
            idempotency_key="forged-import-binding-0001",
            command={
                "binding": binding,
                "corpus_identity": service.corpus.identity,
                "request_expected_revision": 0,
            },
            timestamp=FIXED_TIME,
            expected_revision=0,
        )
    unseeded = ClaimWorkspaceService(
        Storage(str(tmp_path / "unseeded.db")), service.corpus
    )
    with pytest.raises(ClaimWorkspaceError, match="binding"):
        unseeded.store.append(
            claim_id=real_claim,
            event_type="WORKSPACE_CLAIM_IMPORTED",
            idempotency_key="forged-import-corpus-0001",
            command={
                "binding": binding,
                "corpus_identity": forged_identity,
                "request_expected_revision": 0,
            },
            timestamp=FIXED_TIME,
            expected_revision=0,
        )
    with service.store.journal.connect() as connection:
        assert connection.execute(
            """SELECT COUNT(*) FROM claim_loop_events
            WHERE session_id=? AND loop_id=?""",
            ("casepath-workspace-local", "workspace.fake-claim"),
        ).fetchone()[0] == 0


def test_legacy_reset_cannot_delete_system_workspace_journal(
    service: ClaimWorkspaceService,
) -> None:
    before = service.rebuild(timestamp=FIXED_TIME)
    with pytest.raises(ReservedSessionResetError):
        service.storage.reset(session_id="casepath-workspace-local")
    after = service.rebuild(timestamp=FIXED_TIME)
    assert canonical(after | {"timestamp": FIXED_TIME}) == canonical(before)


def test_read_only_replay_opens_without_initialization(
    tmp_path: Path,
    seeded_database: Path,
    corpus: PublicCorpus,
) -> None:
    path = tmp_path / "read-only.db"
    shutil.copy2(seeded_database, path)
    mode_before = path.stat().st_mode
    bytes_before = path.read_bytes()
    service = ClaimWorkspaceService.open_read_only(path, corpus)
    claim_id = sorted(corpus.bindings)[0]
    assert service.store.recover(claim_id)["claim_id"] == claim_id
    assert path.read_bytes() == bytes_before
    assert path.stat().st_mode == mode_before


def test_workspace_api_replays_exact_response_bytes(
    service: ClaimWorkspaceService,
) -> None:
    app = FastAPI()
    app.include_router(
        create_claim_loop_router(
            storage_getter=lambda: service.storage,
            workspace_service_getter=lambda: service,
        )
    )
    client = TestClient(app)
    page = client.get("/api/claim-loops/v1/workspace/claims?limit=3")
    assert page.status_code == 200
    claim_id = page.json()["items"][0]["claim_id"]
    headers = {"X-CasePath-Idempotency-Key": "api-owner-replay-0001"}
    body = {"owner": "Lin", "expected_revision": 1}
    first = client.post(
        f"/api/claim-loops/v1/workspace/claims/{claim_id}/owner",
        headers=headers,
        json=body,
    )
    assert first.status_code == 200
    later = client.post(
        f"/api/claim-loops/v1/workspace/claims/{claim_id}/start",
        headers={"X-CasePath-Idempotency-Key": "api-start-later-0001"},
        json={"expected_revision": 2},
    )
    assert later.status_code == 200
    replay = client.post(
        f"/api/claim-loops/v1/workspace/claims/{claim_id}/owner",
        headers=headers,
        json=body,
    )
    assert replay.status_code == 200
    assert replay.content == first.content


def test_artifact_route_is_claim_scoped_and_safe(service: ClaimWorkspaceService) -> None:
    app = FastAPI()
    app.include_router(
        create_claim_loop_router(
            storage_getter=lambda: service.storage,
            workspace_service_getter=lambda: service,
        )
    )
    client = TestClient(app)
    claims = sorted(service.corpus.bindings)
    artifact = service.corpus.bindings[claims[0]]["observable_artifacts"][0]
    valid = client.get(
        f"/api/claim-loops/v1/workspace/claims/{claims[0]}/artifacts/{artifact['artifact_id']}"
    )
    assert valid.status_code == 200
    assert valid.headers["etag"] == f'"{artifact["sha256"]}"'
    assert "filename*=UTF-8''" in valid.headers["content-disposition"]
    wrong_claim = client.get(
        f"/api/claim-loops/v1/workspace/claims/{claims[1]}/artifacts/{artifact['artifact_id']}"
    )
    assert wrong_claim.status_code == 404


def _scaled_rows(state: dict[str, object], count: int) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for index in range(count):
        value = deepcopy(state)
        claim_id = f"scale-{index:05d}"
        value["claim_id"] = claim_id
        value["loop_id"] = "workspace." + claim_id
        value["binding"]["claim_id"] = claim_id
        binding_material = {
            key: item for key, item in value["binding"].items() if key != "binding_sha256"
        }
        value["binding"]["binding_sha256"] = digest_value(binding_material)
        value["state_sha256"] = digest_value(
            {key: item for key, item in value.items() if key != "state_sha256"}
        )
        rows.append(_row(value, now=FIXED_TIME))
    return rows


@pytest.mark.parametrize(
    ("count", "budget_seconds"),
    ((150, 0.300), (1_000, 0.500), (10_000, 1.000)),
)
def test_projection_sort_scale_targets(
    service: ClaimWorkspaceService,
    count: int,
    budget_seconds: float,
) -> None:
    state = service.states()[0]
    rows = _scaled_rows(state, count)
    samples: list[float] = []
    for _ in range(20):
        start = time.perf_counter()
        sorted(rows, key=lambda row: _sort_key(row, "priority"))[:25]
        samples.append(time.perf_counter() - start)
    p95 = sorted(samples)[math.ceil(0.95 * len(samples)) - 1]
    assert p95 <= budget_seconds, {"count": count, "samples": samples, "p95": p95}
