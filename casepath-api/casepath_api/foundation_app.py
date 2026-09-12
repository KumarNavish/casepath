from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .foundation.router import (
    IDEMPOTENCY_HEADER,
    SESSION_HEADER,
    create_foundation_router,
    service_from_environment,
)
from .foundation.network_guard import (
    install_external_network_guard,
    network_guard_status,
)


if os.getenv("CASEPATH_FOUNDATION_DENY_EXTERNAL_NETWORK", "0") == "1":
    install_external_network_guard()


app = FastAPI(
    title="CasePath provider-free live foundation API",
    version="1.0.0",
    description=(
        "Deterministic public-development integration only; no model, provider, "
        "human/expert, or scientific-performance claim."
    ),
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4173", "http://127.0.0.1:4173"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", SESSION_HEADER, IDEMPOTENCY_HEADER],
    allow_credentials=False,
)
app.include_router(create_foundation_router(service_from_environment()))


@app.get("/healthz")
def healthz() -> dict[str, object]:
    return {
        "status": "ok",
        "service": "casepath-provider-free-foundation-v1",
        "model_calls": 0,
        "provider_calls": 0,
        "provider_credentials_read": False,
        "cost_usd": 0.0,
        "central_hypothesis": "UNTESTED",
        "network_guard": network_guard_status(),
    }
