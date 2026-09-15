from __future__ import annotations

import asyncio
import os
import re
from datetime import datetime, timezone
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from . import __version__
from .canonicalizer import (
    MODEL_MODE_OPENROUTER,
    MODEL_MODE_REFERENCE,
    OPENROUTER_MODEL,
    OPENROUTER_PROVIDER,
    cumulative_usd_cap,
)
from .claim_loop import (
    DEFAULT_EVIDENCE_TOOL_ID,
    StructuredMouldArtifactInterpreterV2,
    UnavailableEvidenceAdapter,
)
from .claim_loop_router import create_claim_loop_router
from .claim_loop_service import ClaimLoopService
from .claim_workspace_v1 import ClaimWorkspaceService
from .data import (
    ARTIFACTS,
    CLAIMS,
    DEMO_CLAIM,
    LATER_CLAIM,
    public_artifact,
    public_claim,
)
from .document_lifecycle_shadow_v1 import create_document_lifecycle_shadow_router
from .foundation.router import create_foundation_router, service_from_environment
from .insurance_correction_v1 import (
    MouldNeutralAssessmentCorrectionAdapterV1,
    MouldNeutralAssessmentRollbackAdapterV1,
)
from .langchain_runtime import (
    OPENROUTER_ENDPOINT_TAG,
    OPENROUTER_EXPECTED_UPSTREAM_PROVIDER,
    OPENROUTER_PROVIDER_MAX_IN_FLIGHT,
    external_tracing_environment_disabled,
    openrouter_provider_policy,
)
from .live_events import TERMINAL_RUN_STATUSES, encode_sse
from .local_artifact_registry import LocalArtifactRegistryAdapterV1
from .multi_agent import (
    AGENT_RUNTIME_PROFILE,
    AI_AGENT_IDS,
    DETERMINISTIC_GATE_IDS,
    LANGCHAIN_OPENROUTER_VERSION,
    LANGCHAIN_VERSION,
    LANGGRAPH_VERSION,
    MULTI_AGENT_AUTHORITY_MODE,
    MULTI_AGENT_IMPLEMENTATION,
    MULTI_AGENT_SCHEMA_VERSION,
    DeterministicStructuredAgent,
    NemotronMultiAgentOrchestrator,
)
from .native_workspace_inquiry_router_v1 import (
    RESEARCH_MODE_HEADER,
    create_native_workspace_inquiry_router,
)
from .native_workspace_inquiry_v1 import NativeWorkspaceInquiryServiceV1
from .native_inference_v1 import (
    OPENROUTER_MINI_MODEL,
    ProviderConfig,
    openrouter_http_once_transport,
)
from .native_claim_loop_bridge_v1 import (
    NativeClaimLoopBridgeV1,
    NativeSourceCorrectionAdapterV1,
    NativeSourceSetAdapterV1,
    NativeSourceSetInterpreterV1,
)
from .native_live_workspace_v1 import (
    NativeLiveWorkspaceServiceV1,
    create_native_live_workspace_router,
)
from .pipeline_v15 import (
    COMPONENT_VERSIONS,
    DETERMINISTIC_PROFILE,
    ORCHESTRATOR,
    PROFILE,
    RELEASE,
    ClaimPipeline,
)
from .storage import ActiveRunResetError, ReservedSessionResetError, Storage
from .source_preserving_shadow_v1 import create_source_preserving_shadow_router
from .workspace_claim_loop_v1 import (
    DeterministicTemplateCyclePipelineRouter,
    WORKSPACE_CLAIM_LOOP_SESSION_ID,
    WorkspaceClaimLoopServiceV1,
    WorkspaceEvidenceWithdrawalCorrectionAdapterV1,
)
from .workspace_evidence_authority_v1 import (
    LoopbackSourceByteAcquisitionAdapterV1,
    ServerInterpretedWorkspaceEvidenceV1,
)
from .workspace_corpus import PublicCorpus, default_workspace_corpus_root
from .workspace_packet_preview import create_packet_preview_router


class _LocalNoStoreStaticFiles(StaticFiles):
    """Prevent a restarted local product from executing a stale controller."""

    async def get_response(self, path: str, scope: dict[str, Any]) -> Response:
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-store, max-age=0"
        response.headers["Pragma"] = "no-cache"
        return response


storage = Storage()
pipeline = ClaimPipeline(storage)
# The public flagship remains the configured runtime. The fixed held-out fixture
# is a deterministic causal-comparison surface: routing it here by its exact
# server-owned claim identity prevents a client-supplied knowledge mode from
# activating another paid inference DAG.
held_out_pipeline = ClaimPipeline(
    storage,
    model_mode=MODEL_MODE_REFERENCE,
    pace_seconds=0,
)
claim_loop_cycle_pipeline = ClaimPipeline(
    storage,
    model_mode=MODEL_MODE_REFERENCE,
    agent_orchestrator=NemotronMultiAgentOrchestrator(
        storage,
        agent_runner=DeterministicStructuredAgent(),
    ),
    pace_seconds=0,
)
claim_loop_protocol_adapter = LocalArtifactRegistryAdapterV1(
    Path(
        os.getenv(
            "CASEPATH_ARTIFACT_REGISTRY_PATH",
            str(storage.path.parent / "claim-loop-artifact-registry-v1"),
        )
    )
)
claim_loop_correction_adapter = MouldNeutralAssessmentCorrectionAdapterV1()
claim_loop_correction_rollback_adapter = MouldNeutralAssessmentRollbackAdapterV1()
claim_workspace_corpus = PublicCorpus(default_workspace_corpus_root())
workspace_cycle_pipeline_router = DeterministicTemplateCyclePipelineRouter(
    storage,
    claim_loop_cycle_pipeline,
)
workspace_evidence_adapter = LoopbackSourceByteAcquisitionAdapterV1(
    Path(
        os.getenv(
            "CASEPATH_WORKSPACE_EVIDENCE_PATH",
            str(storage.path.parent / "workspace-evidence-v1"),
        )
    )
)
workspace_evidence_interpreter = ServerInterpretedWorkspaceEvidenceV1(
    workspace_evidence_adapter
)
workspace_correction_adapter = WorkspaceEvidenceWithdrawalCorrectionAdapterV1()


def claim_loop_service() -> ClaimLoopService:
    return ClaimLoopService(
        storage,
        adapters={DEFAULT_EVIDENCE_TOOL_ID: UnavailableEvidenceAdapter()},
        artifact_interpreter=StructuredMouldArtifactInterpreterV2(),
        cycle_pipeline=claim_loop_cycle_pipeline,
        source_pipeline=claim_loop_cycle_pipeline,
        protocol_adapter=claim_loop_protocol_adapter,
        correction_adapters={
            claim_loop_correction_adapter.adapter_id: claim_loop_correction_adapter,
            claim_loop_correction_rollback_adapter.adapter_id: (
                claim_loop_correction_rollback_adapter
            ),
        },
        cycle_transport_mode="deterministic_test_double",
    )


def claim_workspace_service() -> ClaimWorkspaceService:
    return ClaimWorkspaceService(storage, corpus=claim_workspace_corpus)


@lru_cache(maxsize=1)
def native_claim_loop_runtime() -> tuple[
    NativeSourceSetAdapterV1,
    NativeSourceCorrectionAdapterV1,
    ClaimLoopService,
]:
    adapter = NativeSourceSetAdapterV1()
    correction_adapter = NativeSourceCorrectionAdapterV1()
    native_loop = ClaimLoopService(
        storage,
        adapters={adapter.adapter_id: adapter},
        artifact_interpreter=NativeSourceSetInterpreterV1(),
        cycle_pipeline=workspace_cycle_pipeline_router,
        correction_adapters={
            correction_adapter.adapter_id: correction_adapter,
        },
        authorized_owned_sessions=(WORKSPACE_CLAIM_LOOP_SESSION_ID,),
        reconciliation_scope="authorized_only",
        cycle_transport_mode="deterministic_test_double",
    )
    return adapter, correction_adapter, native_loop


@lru_cache(maxsize=1)
def workspace_claim_loop_service() -> WorkspaceClaimLoopServiceV1:
    normal_loop = ClaimLoopService(
        storage,
        adapters={workspace_evidence_adapter.adapter_id: workspace_evidence_adapter},
        artifact_interpreter=workspace_evidence_interpreter,
        cycle_pipeline=workspace_cycle_pipeline_router,
        correction_adapters={
            workspace_correction_adapter.adapter_id: workspace_correction_adapter,
        },
        authorized_owned_sessions=(WORKSPACE_CLAIM_LOOP_SESSION_ID,),
        reconciliation_scope="authorized_only",
        cycle_transport_mode="deterministic_test_double",
    )
    return WorkspaceClaimLoopServiceV1(
        workspace=claim_workspace_service(),
        claim_loop=normal_loop,
        pipeline_router=workspace_cycle_pipeline_router,
        adapter=workspace_evidence_adapter,
        interpreter=workspace_evidence_interpreter,
        correction_adapter=workspace_correction_adapter,
        native_claim_loop=native_claim_loop_runtime()[2],
    )


@lru_cache(maxsize=1)
def native_workspace_inquiry_service() -> NativeWorkspaceInquiryServiceV1:
    trace_path = os.getenv("CASEPATH_NATIVE_RECORDED_TRACE_PATH")
    if not trace_path:
        raise ValueError("recorded native inquiry provider is not configured")
    database_path = Path(
        os.getenv(
            "CASEPATH_NATIVE_INQUIRY_DB_PATH",
            str(storage.path.parent / "native-workspace-inquiry-v1.sqlite3"),
        )
    )
    return NativeWorkspaceInquiryServiceV1(
        corpus=claim_workspace_corpus,
        database=database_path,
        trace_manifest=Path(trace_path),
    )


@lru_cache(maxsize=1)
def native_live_workspace_service() -> NativeLiveWorkspaceServiceV1:
    if os.getenv("CASEPATH_NATIVE_LIVE_ENABLED") != "1":
        raise ValueError("native live workspace entry is not enabled")
    runtime_root = Path(
        os.getenv(
            "CASEPATH_NATIVE_LIVE_ROOT",
            str(storage.path.parent / "native-live-workspace-v1"),
        )
    )
    openrouter_enabled = (
        os.getenv("CASEPATH_NATIVE_LIVE_ENABLE_OPENROUTER_TRANSPORT") == "1"
    )
    transport = openrouter_http_once_transport if openrouter_enabled else None
    if openrouter_enabled:
        try:
            max_provider_calls = int(
                os.environ["CASEPATH_NATIVE_LIVE_MAX_PROVIDER_CALLS"]
            )
            max_total_cost_usd = float(
                os.environ["CASEPATH_NATIVE_LIVE_MAX_TOTAL_COST_USD"]
            )
            maximum_call_cost_usd = float(
                os.environ["CASEPATH_NATIVE_LIVE_MAX_CALL_COST_USD"]
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(
                "native OpenRouter transport requires explicit call and cost bounds"
            ) from exc
    else:
        max_provider_calls = None
        max_total_cost_usd = None
        maximum_call_cost_usd = None
    return NativeLiveWorkspaceServiceV1(
        corpus=claim_workspace_corpus,
        database=runtime_root / "native-live-workspace-v1.sqlite3",
        runtime_root=runtime_root,
        provider_config=ProviderConfig(
            output_schema_path=str(runtime_root / "actor-output-schema-v1.json"),
            working_directory=str(Path(__file__).parents[2]),
            final_output_path=str(runtime_root / "calls" / "unbound.json"),
            model=(OPENROUTER_MINI_MODEL if openrouter_enabled else "gpt-5.6-sol"),
            reasoning_effort=("low" if openrouter_enabled else "xhigh"),
            codex_executable=os.getenv("CASEPATH_CODEX_EXECUTABLE", "codex"),
            timeout_seconds=300,
            transport_kind=("openrouter" if openrouter_enabled else "codex"),
            max_input_tokens=32_768,
            max_output_tokens=3_072,
            maximum_call_cost_usd=maximum_call_cost_usd,
        ),
        transport=transport,
        max_provider_calls=max_provider_calls,
        max_total_cost_usd=max_total_cost_usd,
    )


@lru_cache(maxsize=1)
def native_claim_loop_bridge_service() -> NativeClaimLoopBridgeV1:
    adapter, correction_adapter, native_loop = native_claim_loop_runtime()
    return NativeClaimLoopBridgeV1(
        native_material=native_live_workspace_service().bridge_material,
        claim_loop=native_loop,
        pipeline_router=workspace_cycle_pipeline_router,
        adapter=adapter,
        correction_adapter=correction_adapter,
        workspace_binding=workspace_claim_loop_service().native_binding,
    )


DEFAULT_RELEASE_ID = "casepath-v20-reference-20260811"
FRONTEND_CONTRACT = "focused-claim-workspace-v20"
SESSION_HEADER = "X-CasePath-Session"
SESSION_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$")
COMMIT_PATTERN = re.compile(r"^[0-9a-fA-F]{40}$")


def run_pipeline_for_claim(claim_id: str) -> ClaimPipeline:
    return held_out_pipeline if claim_id == LATER_CLAIM["claim_id"] else pipeline


app = FastAPI(
    title="CasePath full-process demo API",
    version=__version__,
    description="Fictional generated-data research demonstration only.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://casepath.onrender.com",
        "https://casepath-swiss-claim-lab.onrender.com",
        "https://casepath-guided-v13-preview.onrender.com",
        "https://casepath-full-lifecycle-v15.onrender.com",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=[
        "Content-Type",
        SESSION_HEADER,
        "X-CasePath-Idempotency-Key",
        RESEARCH_MODE_HEADER,
    ],
    allow_credentials=False,
)
app.include_router(create_foundation_router(service_from_environment()))
app.include_router(create_source_preserving_shadow_router())
app.include_router(create_document_lifecycle_shadow_router())
app.include_router(create_packet_preview_router(claim_workspace_service))
# Provider-neutral work events; original claim services remain authoritative.
from .agent_work.install import install_agent_work
install_agent_work(app, claim_workspace_service, workspace_claim_loop_service,
                   storage.path.parent / "agent-work-v1.sqlite3")

app.include_router(
    create_claim_loop_router(
        lambda: storage,
        service_getter=claim_loop_service,
        workspace_service_getter=claim_workspace_service,
        workspace_loop_service_getter=workspace_claim_loop_service,
    )
)
app.include_router(
    create_native_workspace_inquiry_router(native_workspace_inquiry_service)
)
app.include_router(
    create_native_live_workspace_router(
        native_live_workspace_service,
        native_claim_loop_bridge_service,
    )
)


@app.on_event("startup")
def reconcile_claim_loop_requests() -> None:
    claim_loop_service().reconcile_abandoned_requests(
        now=datetime.now(timezone.utc).isoformat(),
        recover_protocol_effects=True,
    )
    workspace_loop = workspace_claim_loop_service()
    workspace_loop.claim_loop.reconcile_abandoned_requests(
        now=datetime.now(timezone.utc).isoformat(),
        recover_protocol_effects=False,
    )
    # Do not advertise readiness and then make the first handler wait for a
    # cold 150-journal reconstruction.  This is a read-only prewarm of the
    # exact product queue; every later mutation invalidates it via SQLite's
    # data-version token and falls back to authoritative replay.
    workspace_loop.queue(limit=1)


class KnowledgeMode(str, Enum):
    current = "current"
    baseline = "baseline"


class ReviewDecision(str, Enum):
    approve_with_edit = "approve_with_edit"
    reject = "reject"


class BuildingEnvelopeMode(str, Enum):
    conditional = "conditional"
    required_now = "required_now"


class RunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    claim_id: str
    knowledge_mode: KnowledgeMode = KnowledgeMode.current


class ReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: ReviewDecision = ReviewDecision.approve_with_edit
    building_envelope_mode: BuildingEnvelopeMode = BuildingEnvelopeMode.conditional
    confidence: float = Field(default=0.9, ge=0, le=1)
    justification: str = Field(default="", max_length=1500)


def require_session(
    value: str | None = Header(default=None, alias=SESSION_HEADER),
) -> str:
    if value is None:
        raise HTTPException(400, f"{SESSION_HEADER} header is required")
    if not SESSION_PATTERN.fullmatch(value):
        raise HTTPException(
            400,
            f"{SESSION_HEADER} must be an opaque 8-128 character identifier",
        )
    if value in storage.protected_session_ids:
        raise HTTPException(
            409,
            "System-owned workspace state requires its dedicated authority surface",
        )
    return value


def release_metadata() -> dict[str, Any]:
    render_commit = (os.getenv("RENDER_GIT_COMMIT") or "").strip()
    custom_commit = (os.getenv("CASEPATH_SOURCE_COMMIT") or "").strip()
    render_valid = bool(COMMIT_PATTERN.fullmatch(render_commit))
    custom_valid = bool(COMMIT_PATTERN.fullmatch(custom_commit))
    if render_commit:
        source_commit = render_commit.lower() if render_valid else "unknown"
        identity_source = (
            "render_git_commit" if render_valid else "invalid_render_git_commit"
        )
        identity_aligned = render_valid and (
            not custom_valid or custom_commit.lower() == source_commit
        )
    elif custom_valid:
        source_commit = custom_commit.lower()
        identity_source = "casepath_source_commit_fallback"
        identity_aligned = True
    else:
        source_commit = "unknown"
        identity_source = "unavailable"
        identity_aligned = False
    identity_conflict = (
        render_valid and custom_valid and render_commit.lower() != custom_commit.lower()
    )
    model_agentic = pipeline.model_mode == MODEL_MODE_OPENROUTER
    runtime_profile = (
        AGENT_RUNTIME_PROFILE if model_agentic else "deterministic_reference"
    )
    configured_runtime_profile = (
        os.getenv("CASEPATH_AGENT_RUNTIME_PROFILE") or ""
    ).strip() or None
    runtime_profile_aligned = (
        not model_agentic or configured_runtime_profile == AGENT_RUNTIME_PROFILE
    )
    credential_configured = bool((os.getenv("OPENROUTER_API_KEY") or "").strip())
    trace_policy_aligned = external_tracing_environment_disabled()
    return {
        "release_id": os.getenv("CASEPATH_RELEASE_ID") or DEFAULT_RELEASE_ID,
        "release": __version__,
        "pipeline_release": RELEASE,
        "source_commit": source_commit,
        "source_commit_source": identity_source,
        "source_commit_aligned": identity_aligned,
        "source_commit_conflict": identity_conflict,
        "profile": PROFILE if model_agentic else DETERMINISTIC_PROFILE,
        "orchestrator": ORCHESTRATOR,
        "model_mode": pipeline.model_mode,
        "model": OPENROUTER_MODEL
        if pipeline.model_mode == MODEL_MODE_OPENROUTER
        else None,
        "configured_model_identity": OPENROUTER_MODEL,
        "model_provider": OPENROUTER_PROVIDER,
        "runtime_profile": runtime_profile,
        "agentic_runtime": {
            "profile": runtime_profile,
            "compiled_profile": AGENT_RUNTIME_PROFILE,
            "configured_profile": configured_runtime_profile,
            "profile_aligned": runtime_profile_aligned,
            "trace_policy_aligned": trace_policy_aligned,
            "execution_mode": (
                "nemotron_multi_agent" if model_agentic else "deterministic_reference"
            ),
            "authority_mode": (
                MULTI_AGENT_AUTHORITY_MODE
                if model_agentic
                else "deterministic_reference"
            ),
            "implementation": (
                MULTI_AGENT_IMPLEMENTATION
                if model_agentic
                else "deterministic_reference"
            ),
            "schema": MULTI_AGENT_SCHEMA_VERSION if model_agentic else None,
            "framework": {
                "langchain": LANGCHAIN_VERSION,
                "langgraph": LANGGRAPH_VERSION,
                "langchain_openrouter": LANGCHAIN_OPENROUTER_VERSION,
            },
            "required_agent_ids": list(AI_AGENT_IDS) if model_agentic else [],
            "deterministic_gate_ids": list(DETERMINISTIC_GATE_IDS)
            if model_agentic
            else [],
            "safety": {
                "deterministic_contract_authority": True,
                "external_tracing": False,
                "prompt_storage": False,
                "raw_output_storage": False,
                "model_fallback": False,
                "automatic_inference_retry": False,
                "provider_max_in_flight": OPENROUTER_PROVIDER_MAX_IN_FLIGHT,
                "ledger_persistence": "ephemeral_instance",
                "budget_scope": "instance_lifetime",
                "cache_scope": "instance_lifetime",
                "external_key_hard_limit_guard": "configured",
                "credential_configured": credential_configured,
                "provider_routing": {
                    "endpoint_tag": OPENROUTER_ENDPOINT_TAG,
                    "expected_upstream_provider": OPENROUTER_EXPECTED_UPSTREAM_PROVIDER,
                    **{
                        key: value
                        for key, value in openrouter_provider_policy().items()
                        if key != "only"
                    },
                },
            },
        },
        "components": COMPONENT_VERSIONS,
        "session_isolation": {
            "enabled": True,
            "header": SESSION_HEADER,
            "format": "8-128 characters; ASCII letters, digits, dot, underscore, colon, or hyphen",
            "state_scope": "caller_session",
            "model_ledger_scope": "global",
            "session_reset_scope": "caller_session_only",
        },
    }


@app.get("/healthz")
def healthz():
    return {
        "status": "ok",
        **release_metadata(),
        "product": "CasePath full-process lifecycle demo",
        "generated_data_only": True,
        "real_claims_approved": False,
    }


@app.get("/readyz")
def readyz():
    metadata = release_metadata()
    model_agentic = pipeline.model_mode == MODEL_MODE_OPENROUTER
    credential_configured = metadata["agentic_runtime"]["safety"][
        "credential_configured"
    ]
    ready = (
        metadata["agentic_runtime"]["profile_aligned"]
        and metadata["agentic_runtime"]["trace_policy_aligned"]
        and (credential_configured or not model_agentic)
    )
    payload = {
        "status": "ready" if ready else "not_ready",
        "database": "sqlite-demo",
        "claims": len(CLAIMS),
        "artifacts": len(ARTIFACTS),
        "active_playbook": "mould-playbook-v3",
        "model_budget": {
            "cumulative_usd_cap": cumulative_usd_cap(),
            "budget_scope": "instance_lifetime",
            "ledger_persistence": "ephemeral_instance",
            "external_key_hard_limit_guard": "configured",
            "credential_configured": credential_configured,
            **storage.model_call_summary(),
        },
        "agentic_runtime": metadata["agentic_runtime"],
    }
    return payload if ready else JSONResponse(payload, status_code=503)


@app.get("/deployment-health")
def deployment_health():
    return {
        "status": "ok",
        **release_metadata(),
        "frontend_contract": FRONTEND_CONTRACT,
        "api_release": __version__,
        "flagship_claim": DEMO_CLAIM["claim_id"],
        "later_claim": LATER_CLAIM["claim_id"],
        "knowledge_version": "mould-playbook-v3",
    }


@app.get("/api/demo")
def demo(session_id: str = Depends(require_session)):
    try:
        knowledge_value = pipeline.knowledge(session_id=session_id)
    except ValueError:
        raise HTTPException(409, "knowledge integrity boundary") from None
    return {
        **release_metadata(),
        "demo_claim_id": DEMO_CLAIM["claim_id"],
        "later_claim_id": LATER_CLAIM["claim_id"],
        "claim": public_claim(DEMO_CLAIM),
        "knowledge": knowledge_value,
    }


@app.get("/api/claims")
def claims():
    return {"items": [public_claim(DEMO_CLAIM), public_claim(LATER_CLAIM)]}


@app.get("/api/claims/{claim_id}")
def claim(claim_id: str):
    if claim_id not in CLAIMS:
        raise HTTPException(404, "claim not found")
    return public_claim(CLAIMS[claim_id])


@app.get("/api/artifacts/{artifact_id}")
def raw_artifact(artifact_id: str):
    if artifact_id not in ARTIFACTS:
        raise HTTPException(404, "artifact not found")
    artifact = ARTIFACTS[artifact_id]
    return Response(
        artifact["path"].read_bytes(),
        media_type=artifact["media_type"],
        headers={
            "Content-Disposition": f'inline; filename="{artifact["filename"]}"',
            "Cache-Control": "public, max-age=3600",
        },
    )


@app.get("/api/artifacts/{artifact_id}/pages/{page_number}")
def artifact_page(artifact_id: str, page_number: int):
    if artifact_id not in ARTIFACTS:
        raise HTTPException(404, "artifact not found")
    artifact = ARTIFACTS[artifact_id]
    if artifact["media_type"] != "application/pdf":
        raise HTTPException(409, "artifact is not a PDF")
    if page_number < 1 or page_number > artifact["page_count"]:
        raise HTTPException(404, "page not found")
    page_path = (
        artifact["path"].parent / "pages" / artifact_id / f"page-{page_number}.png"
    )
    if not page_path.exists():
        raise HTTPException(404, "rendered page not found")
    return Response(
        page_path.read_bytes(),
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@app.get("/api/artifacts/{artifact_id}/extraction")
def artifact_extraction(artifact_id: str):
    if artifact_id not in ARTIFACTS:
        raise HTTPException(404, "artifact not found")
    artifact = ARTIFACTS[artifact_id]
    payload: dict[str, Any] = public_artifact(artifact)
    if artifact["media_type"] == "application/pdf":
        payload["pages"] = artifact["pages"]
    elif artifact["media_type"] == "message/rfc822":
        payload["email"] = artifact["email"]
    else:
        payload["image_note"] = "The source image is available directly."
    return payload


@app.post("/api/runs", status_code=202)
def create_run(req: RunRequest, session_id: str = Depends(require_session)):
    selected_pipeline = run_pipeline_for_claim(req.claim_id)
    try:
        run_id = selected_pipeline.create(
            req.claim_id,
            knowledge_mode=req.knowledge_mode.value,
            session_id=session_id,
        )
    except KeyError:
        raise HTTPException(404, "claim not found")
    return {
        "run_id": run_id,
        "status": "queued",
        "release": RELEASE,
        "profile": (
            PROFILE
            if selected_pipeline.model_mode == MODEL_MODE_OPENROUTER
            else DETERMINISTIC_PROFILE
        ),
        "knowledge_mode": req.knowledge_mode.value,
        "model_mode": selected_pipeline.model_mode,
    }


@app.get("/api/runs/{run_id}")
def get_run(run_id: str, session_id: str = Depends(require_session)):
    run = storage.get_run(run_id, session_id=session_id)
    if not run:
        raise HTTPException(404, "run not found")
    return run


@app.get("/api/runs/{run_id}/events")
async def stream_run_events(
    run_id: str,
    request: Request,
    after: int = Query(default=0, ge=0),
    session_id: str = Depends(require_session),
):
    if storage.run_stream_state(run_id, session_id=session_id) is None:
        raise HTTPException(404, "run not found")

    async def generate():
        cursor = after
        yield "retry: 1500\n\n"
        while True:
            revision = storage.stream_revision(run_id)
            events = storage.stream_events(
                run_id,
                session_id=session_id,
                after=cursor,
            )
            for event in events:
                cursor = event["sequence"]
                yield encode_sse(event)
            state = storage.run_stream_state(run_id, session_id=session_id)
            if state is None or state["status"] in TERMINAL_RUN_STATUSES:
                # Status and terminal outbox row commit together. Re-read once to
                # close the narrow race where that commit lands between the first
                # event query and this status query.
                terminal_events = storage.stream_events(
                    run_id,
                    session_id=session_id,
                    after=cursor,
                )
                for event in terminal_events:
                    cursor = event["sequence"]
                    yield encode_sse(event)
                return
            if await request.is_disconnected():
                return
            changed_revision = await asyncio.to_thread(
                storage.wait_for_stream_change,
                run_id,
                revision,
                15.0,
            )
            if changed_revision == revision:
                yield ": keepalive\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/runs/{run_id}/review")
def review(run_id: str, req: ReviewRequest, session_id: str = Depends(require_session)):
    if not storage.get_run(run_id, session_id=session_id):
        raise HTTPException(404, "run not found")
    try:
        return pipeline.review(
            run_id,
            req.model_dump(mode="json"),
            session_id=session_id,
        )
    except ValueError as exc:
        raise HTTPException(409, str(exc))


@app.get("/api/knowledge")
def knowledge(session_id: str = Depends(require_session)):
    try:
        return pipeline.knowledge(session_id=session_id)
    except ValueError:
        raise HTTPException(409, "knowledge integrity boundary") from None


@app.get("/api/learning-proof")
def learning_proof(
    baseline_run_id: str = Query(min_length=1),
    later_run_id: str = Query(min_length=1),
    session_id: str = Depends(require_session),
):
    try:
        return pipeline.learning_proof(
            baseline_run_id,
            later_run_id,
            session_id=session_id,
        )
    except ValueError as exc:
        raise HTTPException(409, str(exc))


@app.post("/api/demo/reset")
def reset_demo(session_id: str = Depends(require_session)):
    ledger_records_before = storage.model_call_summary()["records"]
    try:
        removed = storage.reset(session_id=session_id)
    except ActiveRunResetError:
        raise HTTPException(
            409,
            "Cannot reset demo state while this session has a queued or running analysis",
        ) from None
    except ReservedSessionResetError:
        raise HTTPException(
            409, "System-owned workspace state cannot be reset"
        ) from None
    return {
        "status": "reset",
        "session_scope": "caller_only",
        "removed": removed,
        "active_playbook": pipeline.knowledge(session_id=session_id)["active_playbook"][
            "version"
        ],
        "model_ledger_scope": "global",
        "model_ledger_preserved": storage.model_call_summary()["records"]
        == ledger_records_before,
        "model_ledger_records": ledger_records_before,
    }


@app.get("/api/model-ledger")
def model_ledger():
    return {
        "scope": "global_budget_ledger",
        "budget_scope": "instance_lifetime",
        "ledger_persistence": "ephemeral_instance",
        "summary": storage.model_call_summary(),
        "items": storage.sanitized_model_ledger(),
    }


def _mount_local_product() -> None:
    """Serve the curated static build only when the local launcher opts in.

    The local product deliberately has one origin: the same FastAPI process
    serves the governed API routes and the exact curated frontend.  Production
    deployments do not set this variable and retain their existing topology.
    """

    configured = (os.getenv("CASEPATH_LOCAL_STATIC_ROOT") or "").strip()
    if not configured:
        return
    stated = Path(configured)
    if not stated.is_absolute():
        raise RuntimeError("CASEPATH_LOCAL_STATIC_ROOT must be absolute")
    if stated.is_symlink() or not stated.is_dir():
        raise RuntimeError("CASEPATH_LOCAL_STATIC_ROOT must be a regular directory")
    resolved = stated.resolve()
    expected = (Path(__file__).resolve().parents[2] / "casepath-public").resolve()
    if resolved != expected:
        raise RuntimeError(
            "CASEPATH_LOCAL_STATIC_ROOT must name this checkout's curated casepath-public tree"
        )
    for relative_path in ("index.html", "deployment.json", "release.json"):
        candidate = resolved / relative_path
        if candidate.is_symlink() or not candidate.is_file():
            raise RuntimeError(
                f"local curated frontend is missing regular file {relative_path}"
            )
    app.mount(
        "/",
        _LocalNoStoreStaticFiles(directory=str(resolved), html=True, check_dir=True),
        name="casepath-local-product",
    )


_mount_local_product()
