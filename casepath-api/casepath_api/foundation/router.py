from __future__ import annotations

import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from .live_service import FoundationLiveError, FoundationLiveService
from .persistence import PersistentFoundationStore
from .trust import (
    TEST_REGISTRY_TRUST_ROOT,
    TEST_REVIEW_TRUST_ROOT,
    FoundationTrustError,
    TrustedDatasetRegistry,
)


SESSION_HEADER = "X-CasePath-Session"
IDEMPOTENCY_HEADER = "X-CasePath-Idempotency-Key"
SESSION_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$")
IDEMPOTENCY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$")


class StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class IntakeRequest(StrictRequest):
    case_id: str = Field(min_length=1, max_length=160)


class ReviewAuthorizationRequest(StrictRequest):
    lifecycle_id: str = Field(min_length=1, max_length=180)
    artifact_version: str = Field(min_length=1, max_length=180)
    accepted_corrections: list[dict[str, Any]] = Field(max_length=20)


class ReviewSubmissionRequest(StrictRequest):
    authorization: dict[str, Any]


class LifecycleRequest(StrictRequest):
    lifecycle_id: str = Field(min_length=1, max_length=180)


class RetrievalRequest(StrictRequest):
    later_case_id: str = Field(min_length=1, max_length=160)


class UITraceRequest(StrictRequest):
    lifecycle_id: str = Field(min_length=1, max_length=180)
    trace: dict[str, Any]


def require_session(
    value: str | None = Header(default=None, alias=SESSION_HEADER),
) -> str:
    if value is None or not SESSION_PATTERN.fullmatch(value):
        raise HTTPException(
            400, f"{SESSION_HEADER} must be an opaque 8-128 character ID"
        )
    return value


def require_idempotency_key(
    value: str | None = Header(default=None, alias=IDEMPOTENCY_HEADER),
) -> str:
    if value is None or not IDEMPOTENCY_PATTERN.fullmatch(value):
        raise HTTPException(
            400, f"{IDEMPOTENCY_HEADER} must be an opaque 8-128 character ID"
        )
    return value


def _parse_clock() -> datetime:
    configured = os.getenv("CASEPATH_FOUNDATION_CLOCK", "").strip()
    if configured:
        parsed = datetime.fromisoformat(configured.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise RuntimeError("CASEPATH_FOUNDATION_CLOCK requires a timezone")
        return parsed
    return datetime.now().astimezone()


def service_from_environment() -> FoundationLiveService | None:
    if os.getenv("CASEPATH_FOUNDATION_LIVE_ENABLED", "0") != "1":
        return None
    if os.getenv("CASEPATH_FOUNDATION_TEST_MODE", "0") != "1":
        raise RuntimeError(
            "Iteration 11 foundation route supports only explicit non-human test mode"
        )
    registry_path = os.getenv("CASEPATH_FOUNDATION_REGISTRY_PATH", "").strip()
    database_path = os.getenv("CASEPATH_FOUNDATION_DB_PATH", "").strip()
    if not registry_path or not database_path:
        raise RuntimeError("foundation registry and database paths are required")
    now = _parse_clock()
    registry = TrustedDatasetRegistry(
        path=Path(registry_path),
        trust_root=TEST_REGISTRY_TRUST_ROOT,
        now=now,
    )
    store = PersistentFoundationStore(Path(database_path))
    return FoundationLiveService(
        registry=registry,
        store=store,
        review_trust_root=TEST_REVIEW_TRUST_ROOT,
        clock=lambda: now,
    )


def create_foundation_router(
    service: FoundationLiveService | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/api/foundation/v1", tags=["foundation-live-v1"])

    def active_service() -> FoundationLiveService:
        if service is None:
            raise HTTPException(
                503,
                "foundation live route is disabled; no synthetic fixture authority configured",
            )
        return service

    def invoke(operation: Any) -> Any:
        try:
            return operation()
        except (FoundationLiveError, FoundationTrustError) as exc:
            raise HTTPException(409, str(exc)) from None

    @router.get("/status")
    def status() -> dict[str, Any]:
        if service is None:
            return {
                "contract": "casepath.foundation-live-status/1.0.0",
                "status": "disabled",
                "reason": "no server-controlled synthetic fixture authority configured",
                "model_calls": 0,
                "provider_calls": 0,
                "provider_credentials_read": False,
                "cost_usd": 0.0,
                "central_hypothesis": "UNTESTED",
            }
        return service.status()

    @router.get("/registry")
    def registry_summary(
        current: FoundationLiveService = Depends(active_service),
    ) -> dict[str, Any]:
        return current.registry.summary()

    @router.get("/compatibility")
    def compatibility(
        current: FoundationLiveService = Depends(active_service),
    ) -> dict[str, Any]:
        return current.compatibility()

    @router.post("/intake")
    def intake(
        request: IntakeRequest,
        session_id: str = Depends(require_session),
        idempotency_key: str = Depends(require_idempotency_key),
        current: FoundationLiveService = Depends(active_service),
    ) -> dict[str, Any]:
        return invoke(
            lambda: current.intake(
                session_id=session_id,
                case_id=request.case_id,
                idempotency_key=idempotency_key,
            )
        )

    @router.post("/review/authorize-test-fixture")
    def authorize_review(
        request: ReviewAuthorizationRequest,
        session_id: str = Depends(require_session),
        idempotency_key: str = Depends(require_idempotency_key),
        current: FoundationLiveService = Depends(active_service),
    ) -> dict[str, Any]:
        return invoke(
            lambda: current.issue_review_authorization(
                session_id=session_id,
                lifecycle_id=request.lifecycle_id,
                artifact_version=request.artifact_version,
                accepted_corrections=request.accepted_corrections,
                idempotency_key=idempotency_key,
            )
        )

    @router.post("/review")
    def submit_review(
        request: ReviewSubmissionRequest,
        session_id: str = Depends(require_session),
        idempotency_key: str = Depends(require_idempotency_key),
        current: FoundationLiveService = Depends(active_service),
    ) -> dict[str, Any]:
        return invoke(
            lambda: current.submit_review(
                session_id=session_id,
                authorization=request.authorization,
                idempotency_key=idempotency_key,
            )
        )

    @router.post("/regression")
    def regression(
        request: LifecycleRequest,
        session_id: str = Depends(require_session),
        idempotency_key: str = Depends(require_idempotency_key),
        current: FoundationLiveService = Depends(active_service),
    ) -> dict[str, Any]:
        return invoke(
            lambda: current.regression(
                session_id=session_id,
                lifecycle_id=request.lifecycle_id,
                idempotency_key=idempotency_key,
            )
        )

    @router.post("/promote")
    def promote(
        request: LifecycleRequest,
        session_id: str = Depends(require_session),
        idempotency_key: str = Depends(require_idempotency_key),
        current: FoundationLiveService = Depends(active_service),
    ) -> dict[str, Any]:
        return invoke(
            lambda: current.promote(
                session_id=session_id,
                lifecycle_id=request.lifecycle_id,
                idempotency_key=idempotency_key,
            )
        )

    @router.post("/retrieve")
    def retrieve(
        request: RetrievalRequest,
        session_id: str = Depends(require_session),
        idempotency_key: str = Depends(require_idempotency_key),
        current: FoundationLiveService = Depends(active_service),
    ) -> dict[str, Any]:
        return invoke(
            lambda: current.retrieve(
                session_id=session_id,
                later_case_id=request.later_case_id,
                idempotency_key=idempotency_key,
            )
        )

    @router.post("/rollback")
    def rollback(
        request: LifecycleRequest,
        session_id: str = Depends(require_session),
        idempotency_key: str = Depends(require_idempotency_key),
        current: FoundationLiveService = Depends(active_service),
    ) -> dict[str, Any]:
        return invoke(
            lambda: current.rollback(
                session_id=session_id,
                lifecycle_id=request.lifecycle_id,
                idempotency_key=idempotency_key,
            )
        )

    @router.get("/lifecycle/{lifecycle_id}")
    def lifecycle_state(
        lifecycle_id: str,
        session_id: str = Depends(require_session),
        current: FoundationLiveService = Depends(active_service),
    ) -> dict[str, Any]:
        return invoke(
            lambda: current.state(session_id=session_id, lifecycle_id=lifecycle_id)
        )

    @router.get("/lifecycle/{lifecycle_id}/benchmark")
    def benchmark_projection(
        lifecycle_id: str,
        session_id: str = Depends(require_session),
        current: FoundationLiveService = Depends(active_service),
    ) -> dict[str, Any]:
        return invoke(
            lambda: current.benchmark_projection(
                session_id=session_id, lifecycle_id=lifecycle_id
            )
        )

    @router.get("/audit-export")
    def audit_export(
        session_id: str = Depends(require_session),
        current: FoundationLiveService = Depends(active_service),
    ) -> dict[str, Any]:
        return invoke(lambda: current.audit_export(session_id=session_id))

    @router.post("/ui-trace")
    def ui_trace(
        request: UITraceRequest,
        session_id: str = Depends(require_session),
        idempotency_key: str = Depends(require_idempotency_key),
        current: FoundationLiveService = Depends(active_service),
    ) -> dict[str, Any]:
        return invoke(
            lambda: current.record_ui_trace(
                session_id=session_id,
                lifecycle_id=request.lifecycle_id,
                trace=request.trace,
                idempotency_key=idempotency_key,
            )
        )

    return router
