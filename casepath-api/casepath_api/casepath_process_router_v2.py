"""HTTP surface for the exact paper-method planner.

The client supplies case material and held documents only. Source packs, graphs,
rules, mappings, and model configuration stay server-side in the injected runtime.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field


class PlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    customer_message: str = Field(min_length=1, max_length=200000)
    already_held: list[str] = Field(default_factory=list, max_length=256)


class DiffRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    before_customer_message: str = Field(min_length=1, max_length=200000)
    after_customer_message: str = Field(min_length=1, max_length=200000)
    already_held: list[str] = Field(default_factory=list, max_length=256)


def create_process_router_v2(
    plan: Callable[[dict[str, str], list[str]], dict[str, Any]],
    diff: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]],
    status: Callable[[], dict[str, Any]],
) -> APIRouter:
    router = APIRouter(prefix="/api/paper-method", tags=["paper-method"])

    @router.get("/status")
    def get_status() -> dict[str, Any]:
        value = status()
        return {"contract": "casepath.paper-method-status/2.0.0", **value}

    @router.post("/plan")
    def post_plan(req: PlanRequest) -> dict[str, Any]:
        try:
            return plan({"customer_message": req.customer_message}, req.already_held)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from None
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from None

    @router.post("/diff")
    def post_diff(req: DiffRequest) -> dict[str, Any]:
        try:
            before = plan({"customer_message": req.before_customer_message}, req.already_held)
            after = plan({"customer_message": req.after_customer_message}, req.already_held)
            return diff(before, after)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from None
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from None

    return router
