from __future__ import annotations

from hashlib import sha256
import json
import re
import unicodedata
from collections.abc import Callable
from typing import Annotated, Any, Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field, StrictInt, ValidationError

from .claim_loop_service import ClaimLoopService, ClaimLoopServiceError
from .claim_workspace_v1 import ClaimWorkspaceError, ClaimWorkspaceService
from .storage import Storage
from .workspace_claim_loop_v1 import (
    WORKSPACE_CLAIM_LOOP_SESSION_ID,
    WorkspaceClaimLoopError,
    WorkspaceClaimLoopServiceV1,
)
from .workspace_evidence_authority_v1 import EVIDENCE_REGISTRATION_FIELDS

SESSION_HEADER = "X-CasePath-Session"
IDEMPOTENCY_HEADER = "X-CasePath-Idempotency-Key"
_OPAQUE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$")


class _Request(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CreateLoopRequest(_Request):
    source_run_id: str = Field(min_length=1, max_length=200)


class AdvanceLoopRequest(_Request):
    expected_revision: int | None = Field(default=None, ge=1)


class IngestObservationRequest(_Request):
    action_id: str = Field(min_length=1, max_length=200)
    artifact_receipt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    expected_revision: int | None = Field(default=None, ge=1)


class ApplyCorrectionRequest(_Request):
    correction_id: str = Field(min_length=1, max_length=200)


class ReuseCorrectionRequest(_Request):
    correction_id: str = Field(min_length=1, max_length=200)


class StageInsuranceMaterialRequest(_Request):
    filename: str = Field(min_length=1, max_length=200)
    media_type: str = Field(min_length=1, max_length=100)
    content: str = Field(min_length=1, max_length=100_000)
    # An optional browser-computed digest is only an integrity assertion.  The
    # registry always recomputes the authoritative content identity itself.
    claimed_content_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    expected_revision: int | None = Field(default=None, ge=1)


class RegisterInsuranceMaterialRequest(_Request):
    proposal_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    staged_artifact_receipt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    expected_revision: int | None = Field(default=None, ge=1)


class PrepareInsuranceCorrectionRequest(_Request):
    candidate_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    target_assertion_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    target_interpretation_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    semantic_delta_id: str = Field(min_length=1, max_length=120)
    expected_revision: StrictInt = Field(ge=1)


class AssignWorkspaceClaimRequest(_Request):
    owner: str = Field(min_length=1, max_length=80)
    expected_revision: StrictInt = Field(ge=1)


class MutateWorkspaceClaimRequest(_Request):
    expected_revision: StrictInt = Field(ge=1)


class EnsureWorkspaceLoopRequest(_Request):
    expected_workspace_revision: StrictInt = Field(ge=1)
    expected_workspace_state_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class RecordWorkspaceHandlerObservationRequest(EnsureWorkspaceLoopRequest):
    kind: Literal["passage", "condition"]
    target: str = Field(min_length=1, max_length=128)
    verdict: Literal["sufficient", "not_relevant", "true", "false", "unresolved"]
    note: str = Field(max_length=1000)


class WithdrawWorkspaceHandlerObservationRequest(EnsureWorkspaceLoopRequest):
    target_event_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class RecordWorkspaceDraftRequest(_Request):
    expected_revision: StrictInt = Field(ge=1)
    expected_state_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    edited_body: str | None = Field(default=None, max_length=30_000)
    replaces_event_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


class KeepReviewedMemoryRequest(_Request):
    source_handler_event_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    handler: str = Field(min_length=1, max_length=80)
    expected_revision: StrictInt = Field(ge=1)
    expected_state_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class ApplyReviewedMemoryRequest(_Request):
    memory_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    note: str = Field(min_length=1, max_length=1000)
    expected_revision: StrictInt = Field(ge=1)
    expected_state_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class RetireReviewedMemoryRequest(_Request):
    memory_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    reason: str = Field(min_length=1, max_length=1000)
    expected_revision: StrictInt = Field(ge=1)
    expected_state_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class MintWorkspaceEvidenceIntentRequest(_Request):
    action_id: str = Field(pattern=r"^action\.[0-9a-f]{64}$")
    expected_revision: StrictInt = Field(ge=1)
    idempotency_key: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$")


class RegisterWorkspaceEvidenceRequest(_Request):
    registration_schema: Literal[
        "casepath.workspace-evidence-registration/3.0.0"
    ] = Field(alias="schema")
    action_id: str = Field(pattern=r"^action\.[0-9a-f]{64}$")
    expected_revision: StrictInt = Field(ge=1)
    idempotency_key: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$")
    acquisition_intent_id: str = Field(pattern=r"^intent\.[0-9a-f]{64}$")
    acquisition_receipt_id: str = Field(pattern=r"^acquisition\.[0-9a-f]{64}$")
    content_b64: str = Field(min_length=4, max_length=133_344)


class AdvanceWorkspaceLoopRequest(_Request):
    expected_revision: StrictInt = Field(ge=1)
    expected_state_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    action_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    stage_receipt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class PrepareWorkspaceCorrectionRequest(_Request):
    candidate_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    expected_revision: StrictInt = Field(ge=1)
    expected_state_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class ApplyWorkspaceCorrectionRequest(_Request):
    correction_id: str = Field(
        pattern=r"^correction\.[0-9a-f]{64}$",
        max_length=75,
    )


def _bounded_header(value: str | None, *, name: str) -> str:
    if value is None or _OPAQUE_ID.fullmatch(value) is None:
        raise HTTPException(400, f"{name} must be an opaque 8-128 character identifier")
    return value


def _generic_claim_loop_session(
    value: Annotated[str | None, Header(alias=SESSION_HEADER)] = None,
) -> str:
    session_id = _bounded_header(value, name=SESSION_HEADER)
    if session_id == WORKSPACE_CLAIM_LOOP_SESSION_ID:
        raise HTTPException(
            409,
            "workspace-owned loops reject generic routes; use the claim-bound workspace authority surface",
        )
    return session_id


def _idempotency_key(
    value: Annotated[str | None, Header(alias=IDEMPOTENCY_HEADER)] = None,
) -> str:
    return _bounded_header(value, name=IDEMPOTENCY_HEADER)


def _raise_http(error: ClaimLoopServiceError) -> None:
    if error.conflict_envelope is not None:
        raise HTTPException(409, error.conflict_envelope) from error
    detail = str(error)
    if "not found" in detail or "does not exist" in detail:
        raise HTTPException(404, detail) from error
    raise HTTPException(409, detail) from error


def create_claim_loop_router(
    storage_getter: Callable[[], Storage],
    *,
    service_getter: Callable[[], ClaimLoopService] | None = None,
    workspace_service_getter: Callable[[], ClaimWorkspaceService] | None = None,
    workspace_loop_service_getter: Callable[[], WorkspaceClaimLoopServiceV1]
    | None = None,
) -> APIRouter:
    """Create routes for the existing app; no second FastAPI app is introduced."""

    router = APIRouter(prefix="/api/claim-loops/v1", tags=["claim-loop"])

    def service() -> ClaimLoopService:
        if service_getter is not None:
            return service_getter()
        # Resolve per request so tests and deployments can replace the canonical
        # Storage instance without leaving a service bound to an old database.
        return ClaimLoopService(storage_getter())

    def workspace_service() -> ClaimWorkspaceService:
        if workspace_service_getter is not None:
            return workspace_service_getter()
        return ClaimWorkspaceService(storage_getter())

    def workspace_loop_service() -> WorkspaceClaimLoopServiceV1:
        if workspace_loop_service_getter is None:
            raise HTTPException(503, "workspace claim loop is not configured")
        return workspace_loop_service_getter()

    def raise_workspace_http(error: ClaimWorkspaceError) -> None:
        detail = str(error)
        if (
            "does not exist" in detail
            or "outside the public corpus" in detail
            or "outside the claim binding" in detail
        ):
            raise HTTPException(404, detail) from error
        raise HTTPException(409, detail) from error

    def raise_workspace_loop_http(error: WorkspaceClaimLoopError) -> None:
        if error.conflict_envelope is not None:
            raise HTTPException(409, error.conflict_envelope) from error
        detail = str(error)
        if "does not exist" in detail or "not found" in detail:
            raise HTTPException(404, detail) from error
        raise HTTPException(409, detail) from error

    def as_workspace_loop_error(error: ValueError) -> WorkspaceClaimLoopError:
        return (
            error
            if isinstance(error, WorkspaceClaimLoopError)
            else WorkspaceClaimLoopError(str(error))
        )

    # Static workspace paths are declared before /{loop_id}; the plural
    # ClaimLoop control plane remains the only product mutation surface.
    @router.get("/workspace/claims")
    def workspace_claims(
        q: str | None = Query(default=None, max_length=160),
        state: str | None = Query(default=None, max_length=40),
        readiness: str | None = Query(default=None, max_length=40),
        claim_type: str | None = Query(default=None, max_length=80),
        owner: str | None = Query(default=None, max_length=80),
        urgency: str | None = Query(default=None, max_length=40),
        failure: bool | None = Query(default=None),
        pending_evidence: str | None = Query(default=None, max_length=20),
        profile: str | None = Query(default=None, pattern=r"^[0-9a-f]{64}$"),
        sort: str = Query(default="priority", max_length=40),
        cursor: str | None = Query(default=None, max_length=4096),
        limit: int = Query(default=25, ge=1, le=100),
    ) -> dict[str, Any]:
        try:
            queue_service = (
                workspace_loop_service()
                if workspace_loop_service_getter is not None
                else workspace_service()
            )
            return queue_service.queue(
                query=q,
                state=state,
                readiness=readiness,
                claim_type=claim_type,
                owner=owner,
                urgency=urgency,
                failure=failure,
                pending_evidence=pending_evidence,
                profile=profile,
                sort=sort,
                cursor=cursor,
                limit=limit,
            )
        except (ClaimWorkspaceError, WorkspaceClaimLoopError, ValueError) as exc:
            raise_workspace_http(ClaimWorkspaceError(str(exc)))

    @router.get("/workspace/claims/{claim_id}")
    def workspace_claim(claim_id: str) -> dict[str, Any]:
        try:
            detail_service = (
                workspace_loop_service()
                if workspace_loop_service_getter is not None
                else workspace_service()
            )
            return detail_service.detail(claim_id)
        except (ClaimWorkspaceError, WorkspaceClaimLoopError, ValueError) as exc:
            raise_workspace_http(ClaimWorkspaceError(str(exc)))

    @router.get("/workspace/claims/{claim_id}/drafts")
    def workspace_claim_drafts(claim_id: str) -> dict[str, Any]:
        try:
            return workspace_service().drafts(claim_id)
        except (ClaimWorkspaceError, ValueError) as exc:
            raise_workspace_http(ClaimWorkspaceError(str(exc)))

    @router.post("/workspace/claims/{claim_id}/drafts")
    def record_workspace_claim_draft(
        claim_id: str,
        body: RecordWorkspaceDraftRequest,
        idempotency_key: Annotated[str, Depends(_idempotency_key)],
    ) -> dict[str, Any]:
        try:
            return workspace_service().record_draft(
                claim_id,
                expected_revision=body.expected_revision,
                expected_state_sha256=body.expected_state_sha256,
                idempotency_key=idempotency_key,
                edited_body=body.edited_body,
                replaces_event_sha256=body.replaces_event_sha256,
            )
        except (ClaimWorkspaceError, ValueError) as exc:
            raise_workspace_http(ClaimWorkspaceError(str(exc)))

    @router.get("/workspace/memories")
    def organisation_memories(family: str | None = None) -> dict[str, Any]:
        try:
            return workspace_service().reviewed_memories(family=family)
        except (ClaimWorkspaceError, ValueError) as exc:
            raise_workspace_http(ClaimWorkspaceError(str(exc)))

    @router.get("/workspace/claims/{claim_id}/memories")
    def matching_claim_memories(claim_id: str) -> dict[str, Any]:
        try:
            return workspace_service().reviewed_memories(claim_id)
        except (ClaimWorkspaceError, ValueError) as exc:
            raise_workspace_http(ClaimWorkspaceError(str(exc)))

    @router.post("/workspace/claims/{claim_id}/memories")
    def keep_claim_memory(
        claim_id: str, body: KeepReviewedMemoryRequest,
        idempotency_key: Annotated[str, Depends(_idempotency_key)],
    ) -> dict[str, Any]:
        try:
            return workspace_service().keep_reviewed_memory(
                claim_id, source_handler_event_sha256=body.source_handler_event_sha256,
                handler=body.handler, expected_revision=body.expected_revision,
                expected_state_sha256=body.expected_state_sha256,
                idempotency_key=idempotency_key,
            )
        except (ClaimWorkspaceError, ValueError) as exc:
            raise_workspace_http(ClaimWorkspaceError(str(exc)))

    @router.post("/workspace/claims/{claim_id}/memories/apply")
    def apply_claim_memory(
        claim_id: str, body: ApplyReviewedMemoryRequest,
        idempotency_key: Annotated[str, Depends(_idempotency_key)],
    ) -> dict[str, Any]:
        try:
            return workspace_service().apply_reviewed_memory(
                claim_id, memory_sha256=body.memory_sha256, note=body.note,
                expected_revision=body.expected_revision,
                expected_state_sha256=body.expected_state_sha256,
                idempotency_key=idempotency_key,
            )
        except (ClaimWorkspaceError, ValueError) as exc:
            raise_workspace_http(ClaimWorkspaceError(str(exc)))

    @router.post("/workspace/claims/{claim_id}/memories/retire")
    def retire_claim_memory(
        claim_id: str, body: RetireReviewedMemoryRequest,
        idempotency_key: Annotated[str, Depends(_idempotency_key)],
    ) -> dict[str, Any]:
        try:
            return workspace_service().retire_reviewed_memory(
                claim_id, memory_sha256=body.memory_sha256, reason=body.reason,
                expected_revision=body.expected_revision,
                expected_state_sha256=body.expected_state_sha256,
                idempotency_key=idempotency_key,
            )
        except (ClaimWorkspaceError, ValueError) as exc:
            raise_workspace_http(ClaimWorkspaceError(str(exc)))

    @router.get("/workspace/claims/{claim_id}/artifacts/{artifact_id}")
    def workspace_artifact(claim_id: str, artifact_id: str) -> Response:
        try:
            raw, row = workspace_service().corpus.artifact(claim_id, artifact_id)
        except (ClaimWorkspaceError, ValueError) as exc:
            raise_workspace_http(ClaimWorkspaceError(str(exc)))
        return Response(
            raw,
            media_type=row["media_type"],
            headers={
                "Content-Disposition": (
                    "inline; filename*=UTF-8''" + quote(row["file_name"], safe="")
                ),
                "ETag": f'"{row["sha256"]}"',
                "X-Content-Type-Options": "nosniff",
                "Cache-Control": "private, no-store",
            },
        )

    @router.get("/workspace/claims/{claim_id}/artifacts/{artifact_id}/text/pages/{page_number}")
    def workspace_pdf_text_page(
        claim_id: str, artifact_id: str, page_number: int,
    ) -> dict[str, Any]:
        try:
            raw, row = workspace_service().corpus.artifact(claim_id, artifact_id)
        except (ClaimWorkspaceError, ValueError) as exc:
            raise_workspace_http(ClaimWorkspaceError(str(exc)))
        if row["media_type"] != "application/pdf" or len(raw) > 16 * 1024 * 1024:
            raise HTTPException(409, "PDF text is unavailable")
        import fitz

        try:
            with fitz.open(stream=raw, filetype="pdf") as document:
                if document.is_encrypted or page_number < 1 or page_number > min(len(document), 30):
                    raise HTTPException(404, "PDF page is unavailable")
                text = unicodedata.normalize("NFC", document[page_number - 1].get_text("text")[:24_000])
        except (ValueError, RuntimeError) as exc:
            raise HTTPException(409, "PDF text could not be read") from exc
        return {
            "contract": "casepath.workspace-pdf-text-page/1.0.0",
            "claim_id": claim_id,
            "artifact_id": artifact_id,
            "artifact_sha256": row["sha256"],
            "page": page_number,
            "text": text,
            "text_sha256": sha256(text.encode("utf-8")).hexdigest(),
        }

    @router.post("/workspace/claims/{claim_id}/owner")
    def assign_workspace_claim(
        claim_id: str,
        body: AssignWorkspaceClaimRequest,
        idempotency_key: Annotated[str, Depends(_idempotency_key)],
    ) -> dict[str, Any]:
        try:
            return workspace_service().assign(
                claim_id,
                owner=body.owner,
                idempotency_key=idempotency_key,
                expected_revision=body.expected_revision,
            )
        except (ClaimWorkspaceError, ValueError) as exc:
            raise_workspace_http(ClaimWorkspaceError(str(exc)))

    @router.post("/workspace/claims/{claim_id}/start")
    def start_workspace_claim(
        claim_id: str,
        body: MutateWorkspaceClaimRequest,
        idempotency_key: Annotated[str, Depends(_idempotency_key)],
    ) -> dict[str, Any]:
        try:
            return workspace_service().start(
                claim_id,
                idempotency_key=idempotency_key,
                expected_revision=body.expected_revision,
            )
        except (ClaimWorkspaceError, ValueError) as exc:
            raise_workspace_http(ClaimWorkspaceError(str(exc)))

    @router.post("/workspace/claims/{claim_id}/reconcile")
    def reconcile_workspace_claim(
        claim_id: str,
        body: MutateWorkspaceClaimRequest,
        idempotency_key: Annotated[str, Depends(_idempotency_key)],
    ) -> dict[str, Any]:
        try:
            return workspace_service().reconcile(
                claim_id,
                idempotency_key=idempotency_key,
                expected_revision=body.expected_revision,
            )
        except (ClaimWorkspaceError, ValueError) as exc:
            raise_workspace_http(ClaimWorkspaceError(str(exc)))

    @router.post("/workspace/claims/{claim_id}/loop")
    def ensure_workspace_claim_loop(
        claim_id: str,
        body: EnsureWorkspaceLoopRequest,
        idempotency_key: Annotated[str, Depends(_idempotency_key)],
    ) -> dict[str, Any]:
        try:
            return workspace_loop_service().ensure(
                claim_id,
                expected_workspace_revision=body.expected_workspace_revision,
                expected_workspace_state_sha256=(body.expected_workspace_state_sha256),
                idempotency_key=idempotency_key,
            )
        except (WorkspaceClaimLoopError, ValueError) as exc:
            raise_workspace_loop_http(as_workspace_loop_error(exc))

    @router.get("/workspace/claims/{claim_id}/loop")
    def get_workspace_claim_loop(claim_id: str) -> dict[str, Any]:
        try:
            return workspace_loop_service().view(claim_id)
        except (WorkspaceClaimLoopError, ValueError) as exc:
            raise_workspace_loop_http(as_workspace_loop_error(exc))

    @router.get("/workspace/claims/{claim_id}/what-if")
    def workspace_claim_what_if(
        claim_id: str,
        condition: Annotated[str, Query(min_length=1, max_length=64)],
        verdict: Literal["true", "false", "unresolved"],
        before_verdict: Literal["true", "false", "unresolved"] | None = None,
    ) -> dict[str, Any]:
        try:
            return workspace_loop_service().what_if(
                claim_id, condition=condition, verdict=verdict,
                before_verdict=before_verdict,
            )
        except (WorkspaceClaimLoopError, ValueError) as exc:
            raise_workspace_loop_http(as_workspace_loop_error(exc))

    @router.post("/workspace/claims/{claim_id}/handler-observations")
    def record_workspace_handler_observation(
        claim_id: str,
        body: RecordWorkspaceHandlerObservationRequest,
        idempotency_key: Annotated[str, Depends(_idempotency_key)],
    ) -> dict[str, Any]:
        try:
            return workspace_loop_service().record_handler_observation(
                claim_id, kind=body.kind, target=body.target,
                verdict=body.verdict, note=body.note,
                expected_workspace_revision=body.expected_workspace_revision,
                expected_workspace_state_sha256=body.expected_workspace_state_sha256,
                idempotency_key=idempotency_key,
            )
        except (WorkspaceClaimLoopError, ValueError) as exc:
            raise_workspace_loop_http(as_workspace_loop_error(exc))

    @router.post("/workspace/claims/{claim_id}/handler-observations/{event_sha256}/withdraw")
    def withdraw_workspace_handler_observation(
        claim_id: str, event_sha256: str,
        body: WithdrawWorkspaceHandlerObservationRequest,
        idempotency_key: Annotated[str, Depends(_idempotency_key)],
    ) -> dict[str, Any]:
        if body.target_event_sha256 != event_sha256:
            raise HTTPException(422, "handler observation target differs")
        try:
            return workspace_loop_service().withdraw_handler_observation(
                claim_id, target_event_sha256=event_sha256,
                expected_workspace_revision=body.expected_workspace_revision,
                expected_workspace_state_sha256=body.expected_workspace_state_sha256,
                idempotency_key=idempotency_key,
            )
        except (WorkspaceClaimLoopError, ValueError) as exc:
            raise_workspace_loop_http(as_workspace_loop_error(exc))

    @router.post("/workspace/claims/{claim_id}/loop/evidence/intents")
    def mint_workspace_claim_evidence_intent(
        claim_id: str,
        body: MintWorkspaceEvidenceIntentRequest,
    ) -> dict[str, Any]:
        try:
            return workspace_loop_service().mint_evidence_intent(
                claim_id,
                action_id=body.action_id,
                expected_revision=body.expected_revision,
                idempotency_key=body.idempotency_key,
            )
        except (WorkspaceClaimLoopError, ValueError) as exc:
            raise_workspace_loop_http(as_workspace_loop_error(exc))

    @router.post(
        "/workspace/claims/{claim_id}/loop/evidence/intents/{acquisition_intent_id}/acquire"
    )
    def acquire_workspace_claim_evidence(
        claim_id: str,
        acquisition_intent_id: str,
        source_entry_sha256: str | None = None,
    ) -> dict[str, Any]:
        try:
            return workspace_loop_service().acquire_evidence(
                claim_id,
                acquisition_intent_id=acquisition_intent_id,
                source_entry_sha256=source_entry_sha256,
            )
        except (WorkspaceClaimLoopError, ValueError) as exc:
            raise_workspace_loop_http(as_workspace_loop_error(exc))

    @router.post("/workspace/claims/{claim_id}/loop/evidence")
    async def register_workspace_claim_evidence(
        claim_id: str,
        request: Request,
        idempotency_key: Annotated[str, Depends(_idempotency_key)],
    ) -> dict[str, Any]:
        raw = await request.body()
        raw_sha256 = sha256(raw).hexdigest()

        def reject_envelope(reason: str) -> None:
            try:
                workspace_loop_service().interpreter.record_registration_envelope_rejection(
                    claim_id=claim_id,
                    request_sha256=raw_sha256,
                    reason=reason,
                )
            except (OSError, TypeError, ValueError) as exc:
                raise HTTPException(
                    409, "workspace registration rejection audit failed closed"
                ) from exc
            raise HTTPException(422, reason)

        def exact_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
            value: dict[str, Any] = {}
            for key, item in pairs:
                if key in value:
                    raise ValueError("duplicate registration field")
                value[key] = item
            return value

        def reject_constant(value: str) -> None:
            raise ValueError(f"non-finite JSON value {value}")

        try:
            decoded = json.loads(
                raw.decode("utf-8", errors="strict"),
                object_pairs_hook=exact_object,
                parse_constant=reject_constant,
            )
            if not isinstance(decoded, dict) or set(decoded) != set(
                EVIDENCE_REGISTRATION_FIELDS
            ):
                raise ValueError(
                    "workspace evidence registration must contain exactly the seven allowlisted fields"
                )
            body = RegisterWorkspaceEvidenceRequest.model_validate(decoded)
            if body.idempotency_key != idempotency_key:
                raise ValueError(
                    "workspace registration body/header idempotency keys differ"
                )
        except (UnicodeError, json.JSONDecodeError, ValidationError, ValueError) as exc:
            reject_envelope(str(exc))
            raise AssertionError("unreachable")
        try:
            return workspace_loop_service().register_evidence(
                claim_id,
                schema=body.registration_schema,
                action_id=body.action_id,
                expected_revision=body.expected_revision,
                idempotency_key=body.idempotency_key,
                acquisition_intent_id=body.acquisition_intent_id,
                acquisition_receipt_id=body.acquisition_receipt_id,
                content_b64=body.content_b64,
            )
        except (WorkspaceClaimLoopError, ValueError) as exc:
            raise_workspace_loop_http(as_workspace_loop_error(exc))

    @router.post("/workspace/claims/{claim_id}/loop/advance")
    def advance_workspace_claim_loop(
        claim_id: str,
        body: AdvanceWorkspaceLoopRequest,
        idempotency_key: Annotated[str, Depends(_idempotency_key)],
    ) -> dict[str, Any]:
        try:
            return workspace_loop_service().advance(
                claim_id,
                expected_revision=body.expected_revision,
                expected_state_sha256=body.expected_state_sha256,
                action_sha256=body.action_sha256,
                stage_receipt_sha256=body.stage_receipt_sha256,
                idempotency_key=idempotency_key,
            )
        except (WorkspaceClaimLoopError, ValueError) as exc:
            raise_workspace_loop_http(as_workspace_loop_error(exc))

    @router.get("/workspace/claims/{claim_id}/loop/corrections/options")
    def get_workspace_correction_options(claim_id: str) -> dict[str, Any]:
        try:
            return workspace_loop_service().correction_options(claim_id)
        except (WorkspaceClaimLoopError, ValueError) as exc:
            raise_workspace_loop_http(as_workspace_loop_error(exc))

    @router.post("/workspace/claims/{claim_id}/loop/corrections/preview")
    def preview_workspace_correction(
        claim_id: str,
        body: PrepareWorkspaceCorrectionRequest,
        idempotency_key: Annotated[str, Depends(_idempotency_key)],
    ) -> dict[str, Any]:
        try:
            return workspace_loop_service().prepare_correction(
                claim_id,
                candidate_sha256=body.candidate_sha256,
                expected_revision=body.expected_revision,
                expected_state_sha256=body.expected_state_sha256,
                idempotency_key=idempotency_key,
            )
        except (WorkspaceClaimLoopError, ValueError) as exc:
            raise_workspace_loop_http(as_workspace_loop_error(exc))

    @router.post("/workspace/claims/{claim_id}/loop/corrections")
    def apply_workspace_correction(
        claim_id: str,
        body: ApplyWorkspaceCorrectionRequest,
        idempotency_key: Annotated[str, Depends(_idempotency_key)],
    ) -> dict[str, Any]:
        try:
            return workspace_loop_service().apply_workspace_correction(
                claim_id,
                correction_id=body.correction_id,
                idempotency_key=idempotency_key,
            )
        except (WorkspaceClaimLoopError, ValueError) as exc:
            raise_workspace_loop_http(as_workspace_loop_error(exc))

    @router.get("/workspace/claims/{claim_id}/loop/export")
    def export_workspace_claim_loop(claim_id: str) -> dict[str, Any]:
        try:
            return workspace_loop_service().export(claim_id)
        except (WorkspaceClaimLoopError, ValueError) as exc:
            raise_workspace_loop_http(as_workspace_loop_error(exc))

    @router.get("/workspace/claims/{claim_id}/export")
    def export_workspace_claim(claim_id: str) -> dict[str, Any]:
        try:
            return workspace_service().export(claim_id)
        except (ClaimWorkspaceError, ValueError) as exc:
            raise_workspace_http(ClaimWorkspaceError(str(exc)))

    @router.post("/workspace/rebuild")
    def rebuild_workspace_projection() -> dict[str, Any]:
        try:
            return (
                workspace_loop_service().rebuild()
                if workspace_loop_service_getter is not None
                else workspace_service().rebuild()
            )
        except (ClaimWorkspaceError, WorkspaceClaimLoopError, ValueError) as exc:
            raise_workspace_http(ClaimWorkspaceError(str(exc)))

    @router.post("")
    def create_loop(
        body: CreateLoopRequest,
        session_id: Annotated[str, Depends(_generic_claim_loop_session)],
        idempotency_key: Annotated[str, Depends(_idempotency_key)],
    ) -> dict[str, Any]:
        try:
            return service().create(
                session_id=session_id,
                source_run_id=body.source_run_id,
                idempotency_key=idempotency_key,
            )
        except ClaimLoopServiceError as exc:
            _raise_http(exc)

    @router.post("/bootstrap/generated-mould")
    def bootstrap_generated_mould(
        session_id: Annotated[str, Depends(_generic_claim_loop_session)],
        idempotency_key: Annotated[str, Depends(_idempotency_key)],
    ) -> dict[str, Any]:
        try:
            return service().bootstrap_generated_mould(
                session_id=session_id,
                idempotency_key=idempotency_key,
            )
        except ClaimLoopServiceError as exc:
            _raise_http(exc)

    @router.get("/{loop_id}")
    def get_loop(
        loop_id: str,
        session_id: Annotated[str, Depends(_generic_claim_loop_session)],
    ) -> dict[str, Any]:
        try:
            return service().state_response(session_id=session_id, loop_id=loop_id)
        except ClaimLoopServiceError as exc:
            _raise_http(exc)

    @router.post("/{loop_id}/advance")
    def advance_loop(
        loop_id: str,
        body: AdvanceLoopRequest,
        session_id: Annotated[str, Depends(_generic_claim_loop_session)],
        idempotency_key: Annotated[str, Depends(_idempotency_key)],
    ) -> dict[str, Any]:
        try:
            # Production API selects one bounded action only.  Tool execution is
            # explicitly adapter-owned and observations enter through the typed
            # ingestion route; synthetic fixtures are never exposed here.
            return service().advance(
                session_id=session_id,
                loop_id=loop_id,
                idempotency_key=idempotency_key,
                expected_revision=body.expected_revision,
            )
        except ClaimLoopServiceError as exc:
            _raise_http(exc)

    @router.post("/{loop_id}/observations")
    def ingest_observation(
        loop_id: str,
        body: IngestObservationRequest,
        session_id: Annotated[str, Depends(_generic_claim_loop_session)],
        idempotency_key: Annotated[str, Depends(_idempotency_key)],
    ) -> dict[str, Any]:
        try:
            return service().ingest_registered_observation(
                session_id=session_id,
                loop_id=loop_id,
                action_id=body.action_id,
                artifact_receipt_sha256=body.artifact_receipt_sha256,
                idempotency_key=idempotency_key,
                expected_revision=body.expected_revision,
            )
        except ClaimLoopServiceError as exc:
            _raise_http(exc)

    @router.post("/{loop_id}/corrections")
    def apply_correction(
        loop_id: str,
        body: ApplyCorrectionRequest,
        session_id: Annotated[str, Depends(_generic_claim_loop_session)],
        idempotency_key: Annotated[str, Depends(_idempotency_key)],
    ) -> dict[str, Any]:
        try:
            return service().apply_correction(
                session_id=session_id,
                loop_id=loop_id,
                correction_id=body.correction_id,
                idempotency_key=idempotency_key,
            )
        except ClaimLoopServiceError as exc:
            _raise_http(exc)

    @router.post("/{loop_id}/corrections/reuse")
    def reuse_correction(
        loop_id: str,
        body: ReuseCorrectionRequest,
        session_id: Annotated[str, Depends(_generic_claim_loop_session)],
        idempotency_key: Annotated[str, Depends(_idempotency_key)],
    ) -> dict[str, Any]:
        try:
            return service().reuse_correction(
                session_id=session_id,
                loop_id=loop_id,
                correction_id=body.correction_id,
                idempotency_key=idempotency_key,
            )
        except ClaimLoopServiceError as exc:
            _raise_http(exc)

    @router.get("/{loop_id}/decision-ready")
    def decision_ready(
        loop_id: str,
        session_id: Annotated[str, Depends(_generic_claim_loop_session)],
    ) -> dict[str, Any]:
        try:
            return service().packet(session_id=session_id, loop_id=loop_id)
        except ClaimLoopServiceError as exc:
            _raise_http(exc)

    @router.get("/{loop_id}/audit")
    def audit_loop(
        loop_id: str,
        session_id: Annotated[str, Depends(_generic_claim_loop_session)],
    ) -> dict[str, Any]:
        try:
            return service().audit(session_id=session_id, loop_id=loop_id)
        except ClaimLoopServiceError as exc:
            _raise_http(exc)

    @router.get("/{loop_id}/protocol/proposal")
    def insurance_proposal(
        loop_id: str,
        session_id: Annotated[str, Depends(_generic_claim_loop_session)],
    ) -> dict[str, Any]:
        try:
            return service().protocol_proposal(
                session_id=session_id,
                loop_id=loop_id,
            )
        except ClaimLoopServiceError as exc:
            _raise_http(exc)

    @router.post("/{loop_id}/protocol/sources/stage")
    def stage_insurance_material(
        loop_id: str,
        body: StageInsuranceMaterialRequest,
        session_id: Annotated[str, Depends(_generic_claim_loop_session)],
        idempotency_key: Annotated[str, Depends(_idempotency_key)],
    ) -> dict[str, Any]:
        try:
            return service().stage_protocol_material(
                session_id=session_id,
                loop_id=loop_id,
                filename=body.filename,
                media_type=body.media_type,
                content=body.content,
                claimed_content_sha256=body.claimed_content_sha256,
                idempotency_key=idempotency_key,
                expected_revision=body.expected_revision,
            )
        except ClaimLoopServiceError as exc:
            _raise_http(exc)

    @router.post("/{loop_id}/protocol/registrations")
    def register_insurance_material(
        loop_id: str,
        body: RegisterInsuranceMaterialRequest,
        session_id: Annotated[str, Depends(_generic_claim_loop_session)],
        idempotency_key: Annotated[str, Depends(_idempotency_key)],
    ) -> dict[str, Any]:
        try:
            return service().register_protocol_material(
                session_id=session_id,
                loop_id=loop_id,
                proposal_sha256=body.proposal_sha256,
                staged_artifact_receipt_sha256=(body.staged_artifact_receipt_sha256),
                idempotency_key=idempotency_key,
                expected_revision=body.expected_revision,
            )
        except ClaimLoopServiceError as exc:
            _raise_http(exc)

    @router.get("/{loop_id}/protocol/corrections/options")
    def insurance_correction_options(
        loop_id: str,
        session_id: Annotated[str, Depends(_generic_claim_loop_session)],
    ) -> dict[str, Any]:
        try:
            return service().protocol_correction_options(
                session_id=session_id,
                loop_id=loop_id,
            )
        except ClaimLoopServiceError as exc:
            _raise_http(exc)

    @router.post("/{loop_id}/protocol/corrections/proposal")
    def prepare_insurance_correction(
        loop_id: str,
        body: PrepareInsuranceCorrectionRequest,
        session_id: Annotated[str, Depends(_generic_claim_loop_session)],
        idempotency_key: Annotated[str, Depends(_idempotency_key)],
    ) -> dict[str, Any]:
        try:
            return service().prepare_protocol_correction(
                session_id=session_id,
                loop_id=loop_id,
                idempotency_key=idempotency_key,
                candidate_sha256=body.candidate_sha256,
                target_assertion_sha256=body.target_assertion_sha256,
                target_interpretation_sha256=body.target_interpretation_sha256,
                semantic_delta_id=body.semantic_delta_id,
                expected_revision=body.expected_revision,
            )
        except ClaimLoopServiceError as exc:
            _raise_http(exc)

    @router.post("/{loop_id}/protocol/intents/{intent_sha256}/reconcile")
    def reconcile_insurance_intent(
        loop_id: str,
        intent_sha256: str,
        session_id: Annotated[str, Depends(_generic_claim_loop_session)],
        idempotency_key: Annotated[str, Depends(_idempotency_key)],
    ) -> dict[str, Any]:
        if re.fullmatch(r"[0-9a-f]{64}", intent_sha256) is None:
            raise HTTPException(400, "intent identity must be a SHA-256 digest")
        try:
            return service().reconcile_protocol_intent(
                session_id=session_id,
                loop_id=loop_id,
                intent_sha256=intent_sha256,
                idempotency_key=idempotency_key,
            )
        except ClaimLoopServiceError as exc:
            _raise_http(exc)

    @router.post("/{loop_id}/protocol/intents/{intent_sha256}/cancel")
    def cancel_insurance_intent(
        loop_id: str,
        intent_sha256: str,
        session_id: Annotated[str, Depends(_generic_claim_loop_session)],
        idempotency_key: Annotated[str, Depends(_idempotency_key)],
    ) -> dict[str, Any]:
        if re.fullmatch(r"[0-9a-f]{64}", intent_sha256) is None:
            raise HTTPException(400, "intent identity must be a SHA-256 digest")
        try:
            return service().cancel_protocol_intent(
                session_id=session_id,
                loop_id=loop_id,
                intent_sha256=intent_sha256,
                idempotency_key=idempotency_key,
            )
        except ClaimLoopServiceError as exc:
            _raise_http(exc)

    @router.get("/{loop_id}/protocol-state")
    def insurance_protocol_state(
        loop_id: str,
        session_id: Annotated[str, Depends(_generic_claim_loop_session)],
    ) -> dict[str, Any]:
        try:
            return service().protocol_state(
                session_id=session_id,
                loop_id=loop_id,
            )
        except ClaimLoopServiceError as exc:
            _raise_http(exc)

    return router


__all__ = [
    "IDEMPOTENCY_HEADER",
    "SESSION_HEADER",
    "create_claim_loop_router",
]
