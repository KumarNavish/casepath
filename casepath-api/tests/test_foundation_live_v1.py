from __future__ import annotations

import ast
import hashlib
import hmac
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from casepath_api.foundation.case_adapter import (
    benchmark_to_canonical,
    canonical_to_benchmark,
    canonical_to_product,
    product_to_canonical,
)
from casepath_api.foundation.common import canonical_json_bytes, digest_value
from casepath_api.foundation.contracts import (
    IntakeAttachment,
    ModelArtifact,
    PrivacyIntake,
    SourceLocator,
)
from casepath_api.foundation.live_service import FoundationLiveService
from casepath_api.foundation.persistence import PersistentFoundationStore
from casepath_api.foundation.router import create_foundation_router
from casepath_api.foundation.trust import (
    TEST_REGISTRY_AUTHORITY_ID,
    TEST_REGISTRY_TRUST_ROOT,
    TEST_REVIEW_PRINCIPAL_ID,
    TEST_REVIEW_TRUST_ROOT,
    FoundationTrustError,
    TrustedDatasetRegistry,
    build_registry_entry,
    sign_registry_manifest,
)


FIXED_NOW = datetime(2026, 8, 24, 19, 0, tzinfo=timezone.utc)
SOURCE_HASH = "a" * 64


def _locator(case_id: str) -> SourceLocator:
    return SourceLocator(
        artifact_id=f"{case_id}.rules",
        artifact_sha256=SOURCE_HASH,
        locator_kind="text_quote",
        page=1,
        exact_text="The public synthetic source requires evidence.",
    )


def _intake(case_id: str, *, message: str | None = None) -> PrivacyIntake:
    locator = _locator(case_id)
    claim_message = message or f"Public synthetic claim {case_id} reports damage."
    return PrivacyIntake(
        case_id=case_id,
        language="en",
        claim_message=claim_message,
        attachments=(
            IntakeAttachment(
                artifact_id=f"{case_id}.message",
                filename="claim.txt",
                media_type="text/plain",
                source_sha256="b" * 64,
                text=claim_message,
                locators=(locator,),
            ),
        ),
        source_locators=(locator,),
        seeded_identifiers=(),
        declared_synthetic_or_anonymized=False,
    )


def _artifact(case_id: str) -> ModelArtifact:
    provenance = _locator(case_id).model_dump(mode="json")
    process = {
        "artifact_version": "casepath.candidate-artifact/0.1.0",
        "concepts": [
            {
                "concept_id": "decision.coverage",
                "kind": "decision",
                "label": "Coverage decision",
                "provenance": [provenance],
            },
            {
                "concept_id": "fact.loss",
                "kind": "fact",
                "label": "Loss fact",
                "provenance": [provenance],
            },
            {
                "concept_id": "evidence.loss",
                "kind": "evidence_capability",
                "label": "Loss evidence",
                "provenance": [provenance],
            },
            {
                "concept_id": "outcome.covered",
                "kind": "outcome",
                "label": "Covered",
                "provenance": [provenance],
            },
        ],
        "relations": [
            {
                "relation_id": "relation.requires",
                "relation_type": "requires_fact",
                "source_id": "decision.coverage",
                "target_id": "fact.loss",
            },
            {
                "relation_id": "relation.supported",
                "relation_type": "supported_by",
                "source_id": "fact.loss",
                "target_id": "evidence.loss",
            },
            {
                "relation_id": "relation.satisfied",
                "relation_type": "satisfied_by",
                "source_id": "evidence.loss",
                "target_id": "candidate.document.loss",
            },
            {
                "relation_id": "relation.outcome",
                "relation_type": "leads_to",
                "source_id": "decision.coverage",
                "target_id": "outcome.covered",
            },
        ],
        "branch_predicates": [
            {
                "predicate_id": "predicate.coverage",
                "expression": "coverage_applies == true",
                "provenance": [provenance],
            }
        ],
        "terminal_outcome_ids": ["outcome.covered"],
        "abstained_concept_ids": [],
    }
    documents = (
        {
            "item_id": "candidate.document.loss",
            "document_id": "document.loss",
            "label": "Loss proof",
            "state": "missing",
            "request_mode": "now",
            "provenance": [provenance],
        },
    )
    payload = {
        "contract": "casepath.provider-neutral-model-artifact/1.0.0",
        "case_id": case_id,
        "process_artifact": process,
        "evidence_document_plan": documents,
        "provenance": [provenance],
    }
    return ModelArtifact.model_validate(
        {**payload, "artifact_sha256": digest_value(payload)}
    )


def _write_registry(path: Path, *, entries: list[dict[str, Any]] | None = None) -> None:
    payload = {
        "contract": "casepath.trusted-dataset-registry/1.0.0",
        "authority_id": TEST_REGISTRY_AUTHORITY_ID,
        "dataset_id": "casepath.public-development.synthetic-test",
        "dataset_version": "2026-08-24.test-v1",
        "valid_from": "2026-08-24T00:00:00+00:00",
        "valid_until": "2030-01-01T00:00:00+00:00",
        "entries": entries
        or [
            build_registry_entry(
                privacy_intake=_intake(case_id), model_artifact=_artifact(case_id)
            )
            for case_id in ("public.fixture.001", "public.fixture.002")
        ],
    }
    path.write_text(
        json.dumps(
            sign_registry_manifest(payload, key=TEST_REGISTRY_TRUST_ROOT),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )


def _service(
    tmp_path: Path, *, revoked: frozenset[str] = frozenset()
) -> FoundationLiveService:
    registry_path = tmp_path / "registry.json"
    if not registry_path.exists():
        _write_registry(registry_path)
    return FoundationLiveService(
        registry=TrustedDatasetRegistry(
            path=registry_path,
            trust_root=TEST_REGISTRY_TRUST_ROOT,
            now=FIXED_NOW,
        ),
        store=PersistentFoundationStore(tmp_path / "foundation.sqlite3"),
        review_trust_root=TEST_REVIEW_TRUST_ROOT,
        clock=lambda: FIXED_NOW,
        revoked_principals=revoked,
    )


def _client(service: FoundationLiveService) -> TestClient:
    app = FastAPI()
    app.include_router(create_foundation_router(service))
    return TestClient(app)


def _headers(session: str, idempotency: str) -> dict[str, str]:
    return {
        "X-CasePath-Session": session,
        "X-CasePath-Idempotency-Key": idempotency,
    }


def _post(
    client: TestClient,
    path: str,
    payload: dict[str, Any],
    *,
    session: str,
    key: str,
) -> Any:
    return client.post(path, json=payload, headers=_headers(session, key))


def _start(client: TestClient, session: str) -> dict[str, Any]:
    response = _post(
        client,
        "/api/foundation/v1/intake",
        {"case_id": "public.fixture.001"},
        session=session,
        key="intake-key-0001",
    )
    assert response.status_code == 200, response.text
    return response.json()


def _authorization(
    client: TestClient, session: str, intake: dict[str, Any], *, key: str
) -> dict[str, Any]:
    response = _post(
        client,
        "/api/foundation/v1/review/authorize-test-fixture",
        {
            "lifecycle_id": intake["lifecycle_id"],
            "artifact_version": intake["candidate_version_id"],
            "accepted_corrections": [
                {
                    "fixture_id": "iteration11.non-human-review",
                    "semantic_change": False,
                }
            ],
        },
        session=session,
        key=key,
    )
    assert response.status_code == 200, response.text
    return response.json()["authorization"]


def _resign(authorization: dict[str, Any]) -> dict[str, Any]:
    payload = {key: value for key, value in authorization.items() if key != "signature"}
    signature = hmac.new(
        TEST_REVIEW_TRUST_ROOT,
        canonical_json_bytes(payload),
        hashlib.sha256,
    ).hexdigest()
    return {**payload, "signature": signature}


def test_live_api_removes_client_controlled_trust_and_fails_closed(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    client = _client(service)
    invented = _post(
        client,
        "/api/foundation/v1/intake",
        {
            "case_id": "public.fixture.001",
            "declared_synthetic_or_anonymized": True,
        },
        session="privacy-session-01",
        key="privacy-extra-001",
    )
    unknown = _post(
        client,
        "/api/foundation/v1/intake",
        {"case_id": "caller.invented.case"},
        session="privacy-session-02",
        key="privacy-unknown-01",
    )
    assert invented.status_code == 422
    assert unknown.status_code == 409

    blocked_path = tmp_path / "blocked-registry.json"
    blocked_entry = build_registry_entry(
        privacy_intake=_intake(
            "public.fixture.blocked", message="Contact unresolved@example.ch"
        ),
        model_artifact=_artifact("public.fixture.blocked"),
    )
    _write_registry(blocked_path, entries=[blocked_entry])
    blocked = TrustedDatasetRegistry(
        path=blocked_path, trust_root=TEST_REGISTRY_TRUST_ROOT, now=FIXED_NOW
    )
    with pytest.raises(FoundationTrustError, match="privacy scan"):
        blocked.admit("public.fixture.blocked")


def test_registry_rejects_unsigned_tampered_stale_and_mismatched_entries(
    tmp_path: Path,
) -> None:
    good_path = tmp_path / "good.json"
    _write_registry(good_path)
    good = json.loads(good_path.read_text(encoding="utf-8"))
    cases = []

    unsigned = dict(good)
    unsigned.pop("signature")
    cases.append(unsigned)

    tampered = json.loads(json.dumps(good))
    tampered["dataset_version"] = "forged"
    cases.append(tampered)

    stale_payload = {
        key: value
        for key, value in good.items()
        if key not in {"manifest_sha256", "signature"}
    }
    stale_payload["valid_until"] = "2025-01-01T00:00:00+00:00"
    cases.append(sign_registry_manifest(stale_payload, key=TEST_REGISTRY_TRUST_ROOT))

    mismatch_payload = {
        key: value
        for key, value in good.items()
        if key not in {"manifest_sha256", "signature"}
    }
    mismatch_payload["entries"][0]["case_id"] = "mismatch"
    cases.append(sign_registry_manifest(mismatch_payload, key=TEST_REGISTRY_TRUST_ROOT))

    for index, value in enumerate(cases):
        path = tmp_path / f"invalid-{index}.json"
        path.write_text(json.dumps(value), encoding="utf-8")
        with pytest.raises(FoundationTrustError):
            TrustedDatasetRegistry(
                path=path, trust_root=TEST_REGISTRY_TRUST_ROOT, now=FIXED_NOW
            )


def test_authenticated_review_rejects_tamper_wrong_role_replay_mismatch_and_revocation(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    client = _client(service)
    session = "auth-session-0001"
    intake = _start(client, session)

    unsigned = _authorization(client, session, intake, key="auth-issue-0001")
    unsigned.pop("signature")
    assert (
        _post(
            client,
            "/api/foundation/v1/review",
            {"authorization": unsigned},
            session=session,
            key="auth-submit-unsigned",
        ).status_code
        == 409
    )

    tampered = _authorization(client, session, intake, key="auth-issue-0002")
    tampered["accepted_corrections"][0]["semantic_change"] = True
    assert (
        _post(
            client,
            "/api/foundation/v1/review",
            {"authorization": tampered},
            session=session,
            key="auth-submit-tamper",
        ).status_code
        == 409
    )

    wrong_role = _authorization(client, session, intake, key="auth-issue-0003")
    wrong_role["role"] = "caller_selected_reviewer"
    wrong_role = _resign(wrong_role)
    assert (
        _post(
            client,
            "/api/foundation/v1/review",
            {"authorization": wrong_role},
            session=session,
            key="auth-submit-role",
        ).status_code
        == 409
    )

    mismatch = _authorization(client, session, intake, key="auth-issue-0004")
    mismatch["reviewed_artifact_version"] = "knowledge.mismatch"
    mismatch = _resign(mismatch)
    assert (
        _post(
            client,
            "/api/foundation/v1/review",
            {"authorization": mismatch},
            session=session,
            key="auth-submit-mismatch",
        ).status_code
        == 409
    )

    valid = _authorization(client, session, intake, key="auth-issue-0005")
    first = _post(
        client,
        "/api/foundation/v1/review",
        {"authorization": valid},
        session=session,
        key="auth-submit-valid",
    )
    idempotent = _post(
        client,
        "/api/foundation/v1/review",
        {"authorization": valid},
        session=session,
        key="auth-submit-valid",
    )
    replay = _post(
        client,
        "/api/foundation/v1/review",
        {"authorization": valid},
        session=session,
        key="auth-submit-replay",
    )
    assert first.status_code == 200
    assert first.json()["review_receipt"]["human_or_expert_review"] is False
    assert idempotent.status_code == 200
    assert idempotent.json()["idempotent_replay"] is True
    assert replay.status_code == 409

    revoked_root = tmp_path / "revoked"
    revoked_root.mkdir()
    revoked_service = _service(
        revoked_root, revoked=frozenset({TEST_REVIEW_PRINCIPAL_ID})
    )
    revoked_client = _client(revoked_service)
    revoked_session = "auth-revoked-001"
    revoked_intake = _start(revoked_client, revoked_session)
    revoked_token = _authorization(
        revoked_client, revoked_session, revoked_intake, key="auth-revoked-issue"
    )
    revoked = _post(
        revoked_client,
        "/api/foundation/v1/review",
        {"authorization": revoked_token},
        session=revoked_session,
        key="auth-revoked-submit",
    )
    assert revoked.status_code == 409


def test_persistent_live_lifecycle_survives_restart_and_rolls_back_exactly(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    client = _client(service)
    session = "restart-session-01"
    intake = _start(client, session)

    premature = _post(
        client,
        "/api/foundation/v1/promote",
        {"lifecycle_id": intake["lifecycle_id"]},
        session=session,
        key="premature-promote",
    )
    assert premature.status_code == 409

    authorization = _authorization(client, session, intake, key="full-auth-issue")
    review = _post(
        client,
        "/api/foundation/v1/review",
        {"authorization": authorization},
        session=session,
        key="full-review-submit",
    )
    regression = _post(
        client,
        "/api/foundation/v1/regression",
        {"lifecycle_id": intake["lifecycle_id"]},
        session=session,
        key="full-regression",
    )
    promotion = _post(
        client,
        "/api/foundation/v1/promote",
        {"lifecycle_id": intake["lifecycle_id"]},
        session=session,
        key="full-promotion",
    )
    retrieval = _post(
        client,
        "/api/foundation/v1/retrieve",
        {"later_case_id": "public.fixture.002"},
        session=session,
        key="full-retrieval",
    )
    assert review.status_code == regression.status_code == promotion.status_code == 200
    assert retrieval.status_code == 200
    promoted_id = promotion.json()["active_version_id"]
    prior_snapshot = intake["candidate_receipt"]["active_before"]
    assert retrieval.json()["retrieval_receipt"]["active_version_id"] == promoted_id

    restarted = _service(tmp_path)
    restarted_client = _client(restarted)
    state = restarted_client.get(
        f"/api/foundation/v1/lifecycle/{intake['lifecycle_id']}",
        headers={"X-CasePath-Session": session},
    )
    assert state.status_code == 200
    assert state.json()["restart_recovered"] is True
    assert state.json()["session"]["active_version_id"] == promoted_id

    rollback = _post(
        restarted_client,
        "/api/foundation/v1/rollback",
        {"lifecycle_id": intake["lifecycle_id"]},
        session=session,
        key="full-rollback",
    )
    assert rollback.status_code == 200, rollback.text
    assert rollback.json()["exact_prior_version_restored"] is True
    assert rollback.json()["active_version_id"] == prior_snapshot

    projection = restarted_client.get(
        f"/api/foundation/v1/lifecycle/{intake['lifecycle_id']}/benchmark",
        headers={"X-CasePath-Session": session},
    )
    audit = restarted_client.get(
        "/api/foundation/v1/audit-export",
        headers={"X-CasePath-Session": session},
    )
    assert projection.status_code == audit.status_code == 200
    assert projection.json()["central_hypothesis"] == "UNTESTED"
    history_states = {item["state_after"] for item in audit.json()["state_history"]}
    assert {
        "candidate",
        "quarantined",
        "reviewed",
        "regression_passed",
        "promoted",
        "superseded",
        "rolled_back",
    }.issubset(history_states)
    assert audit.json()["execution"] == {
        "model_calls": 0,
        "provider_calls": 0,
        "provider_credentials_read": False,
        "cost_usd": 0.0,
        "sealed_data_accessed": False,
        "human_or_expert_study": False,
    }

    canonical = intake["canonical"]
    product = canonical_to_product(
        __import__(
            "casepath_api.foundation.contracts", fromlist=["CanonicalCaseArtifact"]
        ).CanonicalCaseArtifact.model_validate(canonical)
    )
    benchmark = canonical_to_benchmark(
        __import__(
            "casepath_api.foundation.contracts", fromlist=["CanonicalCaseArtifact"]
        ).CanonicalCaseArtifact.model_validate(canonical)
    )
    assert product_to_canonical(product).model_dump(mode="json") == canonical
    assert benchmark_to_canonical(benchmark).model_dump(mode="json") == canonical


def test_provider_free_live_module_graph_and_compatibility_inventory(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    compatibility = service.compatibility()
    classes = {
        item["artifact_class"]: item["classification"]
        for item in compatibility["matrix"]
    }
    assert classes["foundation_live_api_payload_v1"] == "losslessly_supported"
    assert (
        classes["legacy_api_run_and_review_payloads_v15"] == "intentionally_deprecated"
    )
    assert classes["arbitrary_historical_or_external_payload"] == "unsupported"
    assert all(
        item["foundation_mutation"] is False
        for item in compatibility["legacy_bypass_inventory"]
    )

    foundation_dir = Path(__file__).parents[1] / "casepath_api" / "foundation"
    forbidden = {
        "anthropic",
        "langchain",
        "langchain_openrouter",
        "openai",
        "openrouter",
    }
    imports: set[str] = set()
    for path in foundation_dir.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                imports.add(node.module.split(".")[0])
    assert imports.isdisjoint(forbidden)
    assert service.status()["provider_credentials_read"] is False
