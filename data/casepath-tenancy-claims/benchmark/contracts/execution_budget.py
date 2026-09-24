"""Shared, crash-safe global accounting for paid model dispatches."""

from __future__ import annotations

import fcntl
import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from manifests.digests import digest_json

from .schema import StrictModel

NEMOTRON_INPUT_PRICE_MICROUSD_PER_MILLION = 600_000
NEMOTRON_OUTPUT_PRICE_MICROUSD_PER_MILLION = 3_600_000
NEMOTRON_OPENROUTER_ROUTE = "nvidia/nemotron-3-ultra-550b-a55b@together"
NEMOTRON_OPENROUTER_PRICE_IDENTITY_SHA256 = digest_json(
    {
        "route": NEMOTRON_OPENROUTER_ROUTE,
        "input_usd_per_million": "0.60",
        "output_usd_per_million": "3.60",
    }
)
_SHA256_PATTERN = r"^[0-9a-f]{64}$"
TOKENIZER_ENVELOPE_TOKENS = 4096


def nemotron_cost_microusd(input_tokens: int, output_tokens: int) -> int:
    """Return the ceiling at the frozen Together $0.60/$3.60 price."""

    if input_tokens < 0 or output_tokens < 0:
        raise ValueError("token counts must be nonnegative")
    numerator = (
        input_tokens * NEMOTRON_INPUT_PRICE_MICROUSD_PER_MILLION
        + output_tokens * NEMOTRON_OUTPUT_PRICE_MICROUSD_PER_MILLION
    )
    return (numerator + 999_999) // 1_000_000


class GlobalBudgetCaps(StrictModel):
    """Immutable limits already bound by a study or run budget hash."""

    contract: Literal["casepath.global-execution-caps/1.0.0"]
    binding_sha256: str = Field(pattern=_SHA256_PATTERN)
    max_calls: int = Field(ge=1)
    max_input_tokens_per_call: int = Field(ge=1)
    max_output_tokens_per_call: int = Field(ge=1)
    max_input_tokens: int = Field(ge=1)
    max_output_tokens: int = Field(ge=1)
    max_cost_microusd: int = Field(ge=1)
    input_price_microusd_per_million: Literal[600_000]
    output_price_microusd_per_million: Literal[3_600_000]
    price_identity_sha256: Literal[
        "cf193230f7b70001038d7d2c504cbb012848a8caf414f6cf508ac9e2179eca2b"
    ]
    caps_sha256: str = Field(pattern=_SHA256_PATTERN)

    @model_validator(mode="after")
    def validate_caps(self) -> GlobalBudgetCaps:
        if self.max_input_tokens > self.max_calls * self.max_input_tokens_per_call:
            raise ValueError("global input cap exceeds the per-call envelope")
        if self.max_output_tokens > self.max_calls * self.max_output_tokens_per_call:
            raise ValueError("global output cap exceeds the per-call envelope")
        priced_ceiling = nemotron_cost_microusd(self.max_input_tokens, self.max_output_tokens)
        if self.max_cost_microusd > priced_ceiling:
            raise ValueError("USD cap exceeds the frozen token-price envelope")
        if self.caps_sha256 != digest_json(self.model_dump(mode="json", exclude={"caps_sha256"})):
            raise ValueError("global execution caps hash is stale")
        return self


class DispatchAccount(StrictModel):
    """One reconstructed journal entry; no mutable counter is trusted."""

    state: Literal["prepared", "unknown", "succeeded", "failed"]
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_usage(self) -> DispatchAccount:
        has_usage = self.input_tokens is not None or self.output_tokens is not None
        if has_usage != (self.input_tokens is not None and self.output_tokens is not None):
            raise ValueError("dispatch usage must contain both token counts")
        if self.state in {"prepared", "unknown"} and has_usage:
            raise ValueError("nonterminal dispatch cannot contain measured usage")
        if self.state == "succeeded" and not has_usage:
            raise ValueError("successful dispatch must contain measured usage")
        return self


class GlobalBudgetReceipt(StrictModel):
    """Self-hashed accounting snapshot written from authenticated journals."""

    contract: Literal["casepath.global-execution-budget-receipt/1.0.0"]
    run_identity_sha256: str = Field(pattern=_SHA256_PATTERN)
    caps_sha256: str = Field(pattern=_SHA256_PATTERN)
    max_calls: int = Field(ge=1)
    max_input_tokens: int = Field(ge=1)
    max_output_tokens: int = Field(ge=1)
    max_cost_microusd: int = Field(ge=1)
    prepared_count: int = Field(ge=0)
    unknown_count: int = Field(ge=0)
    succeeded_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)
    per_call_overage_count: int = Field(ge=0)
    reserved_call_count: int = Field(ge=0)
    reserved_input_tokens: int = Field(ge=0)
    reserved_output_tokens: int = Field(ge=0)
    reserved_cost_microusd: int = Field(ge=0)
    caps_respected: bool
    overages: tuple[Literal["calls", "input_tokens", "output_tokens", "cost_microusd"], ...]
    can_reserve_next_call: bool
    receipt_sha256: str = Field(pattern=_SHA256_PATTERN)

    @model_validator(mode="after")
    def validate_hash(self) -> GlobalBudgetReceipt:
        if (
            self.reserved_call_count
            != self.unknown_count + self.succeeded_count + self.failed_count
        ):
            raise ValueError("reserved call count does not match dispatched journals")
        observed_overages = tuple(
            name
            for name, actual, maximum in (
                ("calls", self.reserved_call_count, self.max_calls),
                ("input_tokens", self.reserved_input_tokens, self.max_input_tokens),
                ("output_tokens", self.reserved_output_tokens, self.max_output_tokens),
                ("cost_microusd", self.reserved_cost_microusd, self.max_cost_microusd),
            )
            if actual > maximum
        )
        expected_respected = not observed_overages and self.per_call_overage_count == 0
        if self.overages != observed_overages or self.caps_respected != expected_respected:
            raise ValueError("global budget overage fields are inconsistent")
        if self.receipt_sha256 != digest_json(
            self.model_dump(mode="json", exclude={"receipt_sha256"})
        ):
            raise ValueError("global budget receipt hash is stale")
        return self


class GlobalBudgetExceeded(RuntimeError):
    """The next network dispatch cannot fit within every global cap."""


def freeze_global_caps(
    *,
    binding_sha256: str,
    max_calls: int,
    max_input_tokens_per_call: int,
    max_output_tokens_per_call: int,
    max_input_tokens: int,
    max_output_tokens: int,
    max_cost_microusd: int,
) -> GlobalBudgetCaps:
    payload = {
        "contract": "casepath.global-execution-caps/1.0.0",
        "binding_sha256": binding_sha256,
        "max_calls": max_calls,
        "max_input_tokens_per_call": max_input_tokens_per_call,
        "max_output_tokens_per_call": max_output_tokens_per_call,
        "max_input_tokens": max_input_tokens,
        "max_output_tokens": max_output_tokens,
        "max_cost_microusd": max_cost_microusd,
        "input_price_microusd_per_million": NEMOTRON_INPUT_PRICE_MICROUSD_PER_MILLION,
        "output_price_microusd_per_million": NEMOTRON_OUTPUT_PRICE_MICROUSD_PER_MILLION,
        "price_identity_sha256": NEMOTRON_OPENROUTER_PRICE_IDENTITY_SHA256,
    }
    payload["caps_sha256"] = digest_json(payload)
    return GlobalBudgetCaps.model_validate(payload)


def freeze_global_budget_receipt(
    *,
    run_identity_sha256: str,
    caps: GlobalBudgetCaps,
    entries: tuple[DispatchAccount, ...],
) -> GlobalBudgetReceipt:
    prepared = sum(entry.state == "prepared" for entry in entries)
    unknown = sum(entry.state == "unknown" for entry in entries)
    succeeded = sum(entry.state == "succeeded" for entry in entries)
    failed = sum(entry.state == "failed" for entry in entries)
    reserved_input = 0
    reserved_output = 0
    per_call_overages = 0
    for entry in entries:
        if entry.state == "prepared":
            continue
        if entry.input_tokens is None or entry.output_tokens is None:
            reserved_input += caps.max_input_tokens_per_call
            reserved_output += caps.max_output_tokens_per_call
        else:
            per_call_overages += (
                entry.input_tokens > caps.max_input_tokens_per_call
                or entry.output_tokens > caps.max_output_tokens_per_call
            )
            reserved_input += entry.input_tokens
            reserved_output += entry.output_tokens
    calls = unknown + succeeded + failed
    cost = nemotron_cost_microusd(reserved_input, reserved_output)
    overages = tuple(
        name
        for name, actual, maximum in (
            ("calls", calls, caps.max_calls),
            ("input_tokens", reserved_input, caps.max_input_tokens),
            ("output_tokens", reserved_output, caps.max_output_tokens),
            ("cost_microusd", cost, caps.max_cost_microusd),
        )
        if actual > maximum
    )
    can_reserve = (
        not overages
        and not per_call_overages
        and (
            calls + 1 <= caps.max_calls
            and reserved_input + caps.max_input_tokens_per_call <= caps.max_input_tokens
            and reserved_output + caps.max_output_tokens_per_call <= caps.max_output_tokens
            and cost
            + nemotron_cost_microusd(
                caps.max_input_tokens_per_call, caps.max_output_tokens_per_call
            )
            <= caps.max_cost_microusd
        )
    )
    payload = {
        "contract": "casepath.global-execution-budget-receipt/1.0.0",
        "run_identity_sha256": run_identity_sha256,
        "caps_sha256": caps.caps_sha256,
        "max_calls": caps.max_calls,
        "max_input_tokens": caps.max_input_tokens,
        "max_output_tokens": caps.max_output_tokens,
        "max_cost_microusd": caps.max_cost_microusd,
        "prepared_count": prepared,
        "unknown_count": unknown,
        "succeeded_count": succeeded,
        "failed_count": failed,
        "per_call_overage_count": per_call_overages,
        "reserved_call_count": calls,
        "reserved_input_tokens": reserved_input,
        "reserved_output_tokens": reserved_output,
        "reserved_cost_microusd": cost,
        "caps_respected": not overages and not per_call_overages,
        "overages": overages,
        "can_reserve_next_call": can_reserve,
    }
    payload["receipt_sha256"] = digest_json(payload)
    return GlobalBudgetReceipt.model_validate(payload)


def require_next_call(receipt: GlobalBudgetReceipt) -> None:
    if not receipt.can_reserve_next_call:
        raise GlobalBudgetExceeded(
            "the next provider call cannot fit within the frozen global call/token/USD caps"
        )


def conservative_input_token_bound(serialized_request_bytes: int) -> int:
    """Byte fallback plus a fixed chat-template envelope; safe without a tokenizer."""

    if serialized_request_bytes < 0:
        raise ValueError("serialized request size must be nonnegative")
    return serialized_request_bytes + TOKENIZER_ENVELOPE_TOKENS


@contextmanager
def exclusive_budget_lock(path: Path) -> Iterator[None]:
    """Serialize journal reservation across concurrent resume processes."""

    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)
