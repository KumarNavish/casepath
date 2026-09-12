"""HTTP mount for the opt-in recorded native workspace inquiry entry."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from .native_workspace_inquiry_v1 import (
    NATIVE_RESEARCH_MODE,
    NativeWorkspaceInquiryConflict,
    NativeWorkspaceInquiryError,
    NativeWorkspaceInquiryServiceV1,
)

IDEMPOTENCY_HEADER = "X-CasePath-Idempotency-Key"
RESEARCH_MODE_HEADER = "X-CasePath-Native-Research-Mode"
ROUTE_ROOT = "/api/claim-loops/v1/workspace/claims/{claim_id}/native-inquiry/recorded"


class _Request(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DispatchRecordedInquiryRequest(_Request):
    expected_state_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class AdmitRecordedResponseRequest(_Request):
    request_id: str = Field(pattern=r"^request\.[0-9a-f]{64}$")
    expected_state_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class AdmitRecordedCorrectionRequest(_Request):
    expected_state_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    expected_opaque_target_id: str = Field(pattern=r"^a_[0-9a-f]{20}$")


def _idempotency(
    value: Annotated[str | None, Header(alias=IDEMPOTENCY_HEADER)] = None,
) -> str:
    if value is None or not (8 <= len(value) <= 128) or not all(
        character.isalnum() or character in "._:-" for character in value
    ):
        raise HTTPException(400, f"{IDEMPOTENCY_HEADER} must be an opaque 8-128 character identifier")
    return value


def _research_mode(
    value: Annotated[str | None, Header(alias=RESEARCH_MODE_HEADER)] = None,
) -> None:
    if value != NATIVE_RESEARCH_MODE:
        raise HTTPException(
            404,
            "recorded native inquiry entry requires the explicit recorded-replay research mode",
        )


def create_native_workspace_inquiry_router(
    service_getter: Callable[[], NativeWorkspaceInquiryServiceV1],
) -> APIRouter:
    router = APIRouter(dependencies=[Depends(_research_mode)])

    def service() -> NativeWorkspaceInquiryServiceV1:
        try:
            return service_getter()
        except (NativeWorkspaceInquiryError, ValueError) as exc:
            raise HTTPException(503, str(exc)) from exc

    def invoke(operation: Callable[[], dict]) -> dict:
        try:
            return operation()
        except NativeWorkspaceInquiryConflict as exc:
            raise HTTPException(409, str(exc)) from exc
        except NativeWorkspaceInquiryError as exc:
            raise HTTPException(400, str(exc)) from exc

    @router.get(ROUTE_ROOT)
    def state(claim_id: str) -> dict:
        return invoke(lambda: service().state(claim_id))

    @router.post(ROUTE_ROOT + "/open")
    def open_entry(
        claim_id: str,
        idempotency_key: Annotated[str, Depends(_idempotency)],
    ) -> dict:
        return invoke(
            lambda: service().open(claim_id, idempotency_key=idempotency_key)
        )

    @router.post(ROUTE_ROOT + "/dispatch")
    def dispatch(
        claim_id: str,
        body: DispatchRecordedInquiryRequest,
        idempotency_key: Annotated[str, Depends(_idempotency)],
    ) -> dict:
        return invoke(lambda: service().dispatch(
            claim_id,
            expected_state_sha256=body.expected_state_sha256,
            idempotency_key=idempotency_key,
        ))

    @router.post(ROUTE_ROOT + "/response")
    def response(
        claim_id: str,
        body: AdmitRecordedResponseRequest,
        idempotency_key: Annotated[str, Depends(_idempotency)],
    ) -> dict:
        return invoke(lambda: service().admit_recorded_response(
            claim_id,
            request_id=body.request_id,
            expected_state_sha256=body.expected_state_sha256,
            idempotency_key=idempotency_key,
        ))

    @router.post(ROUTE_ROOT + "/correction")
    def correction(
        claim_id: str,
        body: AdmitRecordedCorrectionRequest,
        idempotency_key: Annotated[str, Depends(_idempotency)],
    ) -> dict:
        return invoke(lambda: service().admit_recorded_correction(
            claim_id,
            expected_state_sha256=body.expected_state_sha256,
            expected_opaque_target_id=body.expected_opaque_target_id,
            idempotency_key=idempotency_key,
        ))

    return router
