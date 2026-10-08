"""One optional facts-role transport. It cannot mutate the frontend or claim DB.

Tool calling: https://openrouter.ai/docs/guides/features/tool-calling
The actual catalogue must be supplied by an explicit preflight, not assumed.
No model output other than tool calls and usage metadata is persisted/displayed.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
import re
from typing import Any

import httpx

from .contracts import Role, Operation, TOOL_MODELS, canonical, tool_definitions
from .runtime import ToolRuntime, WorkBlocked

ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
CATALOGUE = "https://openrouter.ai/api/v1/models"


def choose_model(catalogue: dict, *, model: str | None = None) -> dict:
    """Validate a pinned model, or select the cheapest compatible proof model."""
    if not isinstance(catalogue,dict) or not isinstance(catalogue.get("data"),list):
        raise WorkBlocked("model catalogue does not contain a typed model roster")
    selected_model = model
    candidates = []
    for row in catalogue["data"]:
        if not isinstance(row,dict):continue
        try:
            model = row["id"]
            if selected_model is not None and model != selected_model:continue
            if not isinstance(model,str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_./:+-]{2,180}",model):continue
            if type(row.get("context_length")) is not int or not isinstance(row.get("supported_parameters"),list):continue
            canonical_model = row.get("canonical_slug")
            if canonical_model is not None and (not isinstance(canonical_model,str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_./:+-]{2,180}",canonical_model) or canonical_model.startswith("openrouter/")):
                continue
            params = row.get("supported_parameters", [])
            price = row["pricing"]
            if not isinstance(price, dict):continue
            # This request has no web plugin, cache_control, image, or audio.
            # Those catalogue feature prices are not applicable. Unknown paid
            # features and unknown tier conditions fail closed.
            unused = {"web_search", "input_cache_read", "input_cache_write", "input_cache_write_1h", "image", "audio", "input_audio", "output_audio"}
            base = {key: Decimal(str(value)) for key, value in price.items() if key != "overrides"}
            if any(not amount.is_finite() or amount < 0 for amount in base.values()):continue
            if any(amount != 0 for key, amount in base.items() if key not in {"prompt", "completion", "request"} | unused):continue
            prompt, completion = base["prompt"], base["completion"]
            request_price = base.get("request", Decimal(0))
            overrides = price.get("overrides", [])
            if not isinstance(overrides, list) or len(overrides) > 32 or row.get("pricing_tiers") is not None:continue
            valid = True
            for tier in overrides:
                if (not isinstance(tier, dict) or type(tier.get("min_prompt_tokens")) is not int
                    or tier["min_prompt_tokens"] < 0 or set(tier) - ({"min_prompt_tokens", "prompt", "completion", "request"} | unused)):
                    valid = False; break
                amounts = {key: Decimal(str(value)) for key, value in tier.items() if key != "min_prompt_tokens"}
                if any(not amount.is_finite() or amount < 0 for amount in amounts.values()):
                    valid = False; break
                # UTF-8 request bytes conservatively bound admitted prompt tokens.
                if tier["min_prompt_tokens"] <= 24000:
                    prompt = max(prompt, amounts.get("prompt", prompt))
                    completion = max(completion, amounts.get("completion", completion))
                    request_price = max(request_price, amounts.get("request", request_price))
            if not valid:continue
            request = request_price
            if "tools" not in params or row.get("context_length", 0) < 8192 or model.startswith("openrouter/"):
                continue
            if any(not x.is_finite() or x < 0 for x in (prompt, completion, request)):
                continue
            # Include applicable per-request and token charges in the bound.
            # A free entry must actually price the admitted request at zero.
            maximum = prompt * 24000 + completion * 800 + request
            candidates.append((maximum, model, {"model": model, "canonical_model": canonical_model, "prompt_price": str(prompt), "completion_price": str(completion),
                                                "request_price": str(request), "catalogue_entry_sha256": sha256(canonical(row)).hexdigest(),
                                                "context_length": row["context_length"], "reasoning_supported": "reasoning" in params, "free": maximum == 0}))
        except (KeyError, TypeError, ValueError, InvalidOperation):
            continue
    if not candidates:
        raise WorkBlocked("catalogue has no compatible, explicitly priced tool-capable model")
    candidates.sort(key=lambda item: (item[0], item[1]))
    return candidates[0][2]


@dataclass(frozen=True)
class OpenRouterConfig:
    model: str
    prompt_price: Decimal
    completion_price: Decimal
    request_price: Decimal = Decimal("0")
    total_cost_limit: Decimal = Decimal("0.02")
    max_requests: int = 6
    max_tool_calls: int = 20
    max_output_tokens: int = 800
    max_request_bytes: int = 24000
    timeout_seconds: float = 45.0
    catalogue_entry_sha256: str = ""
    canonical_model: str | None = None
    context_length: int = 32768
    reasoning_supported: bool = False

    def __post_init__(self):
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_./:+-]{2,180}", self.model) or self.model.startswith("openrouter/"):
            raise ValueError("a concrete provider model is required")
        if self.canonical_model is not None and (not isinstance(self.canonical_model,str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_./:+-]{2,180}",self.canonical_model) or self.canonical_model.startswith("openrouter/")):
            raise ValueError("invalid catalogue-bound canonical model identity")
        if any(not x.is_finite() or x < 0 for x in (self.prompt_price, self.completion_price, self.request_price, self.total_cost_limit)):
            raise ValueError("invalid model prices")
        if any(type(value) is not int for value in (self.max_requests,self.max_tool_calls,self.max_output_tokens,self.max_request_bytes)):
            raise ValueError("provider limits must be whole numbers")
        if type(self.reasoning_supported) is not bool:
            raise ValueError("invalid reasoning capability")
        if not 1 <= self.max_requests <= 6 or not 1 <= self.max_tool_calls <= 24 or not 1 <= self.max_output_tokens <= 1024:
            raise ValueError("the external proof must stay bounded")
        if not 4096 <= self.max_request_bytes <= 32000 or not 1 <= self.timeout_seconds <= 60:
            raise ValueError("invalid input/time bound")
        if self.total_cost_limit > Decimal("0.05"):
            raise ValueError("this one-role proof cannot reserve more than five cents")
        if type(self.context_length) is not int or self.context_length < 8192:
            raise ValueError("invalid model context bound")
        if not re.fullmatch(r"[a-f0-9]{64}", self.catalogue_entry_sha256):
            raise ValueError("the model must bind an inspected catalogue entry")

    @property
    def maximum_request_cost(self):
        # Bytes are a deliberately pessimistic bound for text token count.
        return self.prompt_price * self.max_request_bytes + self.completion_price * self.max_output_tokens + self.request_price

    def public(self):
        return {"model": self.model, "canonical_model": self.canonical_model, "provider": "OpenRouter", "role": Role.FACTS.value,
                "catalogue_entry_sha256": self.catalogue_entry_sha256,
                "max_requests": self.max_requests, "max_tool_calls": self.max_tool_calls,
                "max_output_tokens": self.max_output_tokens, "cost_limit_usd": str(self.total_cost_limit),
                "max_request_bytes": self.max_request_bytes, "timeout_seconds": self.timeout_seconds, "context_length": self.context_length, "reasoning_supported": self.reasoning_supported,
                "prompt_price": str(self.prompt_price), "completion_price": str(self.completion_price), "request_price": str(self.request_price)}


class OpenRouterFactsWorker:
    kind = "external"

    def __init__(self, config: OpenRouterConfig, api_key: str, client: httpx.Client | None = None):
        if not isinstance(api_key, str) or not api_key.startswith("sk-or-"):
            raise ValueError("an OpenRouter credential is required")
        self.config = config
        self._key = api_key
        self._client = client

    def __repr__(self):
        return f"OpenRouterFactsWorker(model={self.config.model!r}, credential=<redacted>)"

    def run(self, runtime: ToolRuntime):
        if runtime.role != Role.FACTS:
            raise WorkBlocked("the external adapter is authorized for the facts role only")
        # A partial earlier inference cannot be blindly sent again. Completed
        # facts are recovered by the executor without invoking this adapter.
        if any(e["operation"] == Operation.PROVIDER_REQUEST_STARTED for e in runtime.store.events(runtime.run_id)):
            raise WorkBlocked("this run has a prior provider request; inspect its recorded outcome rather than retrying inference")
        cfg = self.config
        messages = [{"role": "system", "content": (
            "You are the Facts role in CasePath. Use only the supplied tools. First read the customer message, list the original sources and open every attachment. "
            "Select at least one short exact source passage copied character-for-character, then propose it verbatim as a reported assertion. "
            "Offsets count Unicode code points, but the tool may canonicalize a wrong offset only when your exact quote occurs once; never paraphrase the quote. "
            "A customer's claim is not an established fact. Do not infer legal conclusions, causes or missing evidence. "
            "Never output private reasoning or explanations. Call finish_work only after the required tools succeed. "
            "Tool errors are authoritative; do not invent a source or offset. Preserve German/English source wording exactly."
        )}, {"role": "user", "content": "Inspect this claim's original sources and record the most relevant source statements. Claim: " + runtime.claim_id}]
        requests, calls, reserved, observed_cost = 0, 0, Decimal("0"), Decimal("0")
        client = self._client or httpx.Client(timeout=cfg.timeout_seconds, follow_redirects=False, trust_env=False)
        try:
            while requests < cfg.max_requests:
                runtime.store.heartbeat(runtime.run_id, runtime.owner)
                request = {"model": cfg.model, "messages": messages, "tools": tool_definitions(Role.FACTS),
                           "tool_choice": "required", "max_tokens": cfg.max_output_tokens, "stream": False,
                           "provider": {"allow_fallbacks": False, "require_parameters": True, "data_collection": "deny",
                                        "max_price": {"prompt": float(cfg.prompt_price * 1_000_000), "completion": float(cfg.completion_price * 1_000_000)}}}
                if cfg.reasoning_supported:
                    request["reasoning"] = {"enabled": False, "exclude": True}
                data = canonical(request)
                if len(data) + cfg.max_output_tokens > cfg.context_length:
                    raise WorkBlocked("provider request exceeds the conservative model context bound")
                if len(data) > cfg.max_request_bytes:
                    raise WorkBlocked("provider input reached the frozen byte limit; no extra request was sent")
                if reserved + cfg.maximum_request_cost > cfg.total_cost_limit:
                    raise WorkBlocked("the bounded provider-cost reservation is exhausted")
                reserved += cfg.maximum_request_cost
                requests += 1
                request_id = "provider.request." + str(requests)
                runtime.store.begin_provider_call(runtime.run_id, runtime.owner, request_id, sha256(data).hexdigest(),
                                                  model=cfg.model, maximum_cost_usd=str(cfg.maximum_request_cost), parent_event=runtime.parent_event)
                try:
                    response = client.post(ENDPOINT, content=data,
                                           headers={"Authorization": "Bearer " + self._key, "Content-Type": "application/json"})
                except httpx.HTTPError as exc:
                    # Leave the pending provider call unfinished. A timeout or
                    # connection error cannot establish billed usage or failure.
                    runtime.store.append(runtime.run_id, runtime.owner, role=runtime.role.value, operation=Operation.PROVIDER_OUTCOME_UNKNOWN,
                                         object_kind="provider_request", object_id=request_id, status="unknown", worker_kind="external", parent_event=runtime.parent_event,
                                         message="Provider response was not confirmed. No inference retry was attempted.",
                                         after={"exception_type": type(exc).__name__, "usage": None, "cost_usd": None})
                    raise WorkBlocked("provider outcome is unconfirmed; automatic retry is disabled") from exc
                if len(response.content) > 128000:
                    raise WorkBlocked("provider response exceeds the transport bound")
                if response.status_code != 200:
                    runtime.store.complete_call(runtime.run_id, runtime.owner, runtime.role, request_id,
                                                {"ok": False, "http_status": response.status_code, "usage": None},
                                                [{"role": runtime.role.value, "operation": Operation.PROVIDER_RESPONSE_RECEIVED,
                                                  "object_kind": "provider_response", "object_id": request_id, "status": "rejected", "worker_kind": "external", "parent_event":runtime.parent_event,
                                                  "message": f"Provider returned HTTP {response.status_code}; no fallback was made", "after": {"http_status": response.status_code, "usage": None}}])
                    raise WorkBlocked(f"provider returned HTTP {response.status_code}; no fallback or automatic retry")
                try:
                    value = response.json()
                    # Accept only the exact request ID or the permanent ID from
                    # the same hash-bound catalogue entry. No suffix guessing,
                    # cross-model fallback, or arbitrary alias is permitted.
                    identities={cfg.model}
                    if cfg.canonical_model is not None:identities.add(cfg.canonical_model)
                    if value.get("model") not in identities:
                        raise ValueError("provider returned a different model identity")
                    choice = value["choices"][0]
                    returned = choice["message"].get("tool_calls", [])
                    if not isinstance(returned, list) or not 1 <= len(returned) <= 8:
                        raise ValueError("no bounded tool calls")
                    safe_calls = []
                    for item in returned:
                        function = item["function"]
                        if item["type"] != "function" or function["name"] not in ROLE_TOOLS_FACTS:
                            raise ValueError("unavailable tool")
                        if not isinstance(item["id"], str) or not 1 <= len(item["id"]) <= 160 or not isinstance(function["arguments"], str):
                            raise ValueError("invalid call identity")
                        arguments = json.loads(function["arguments"], object_pairs_hook=_unique_pairs)
                        if not isinstance(arguments, dict) or len(canonical(arguments)) > 8000:
                            raise ValueError("oversized or invalid tool arguments")
                        safe_calls.append({"id": item["id"], "type": "function", "function": {"name": function["name"], "arguments": function["arguments"]}})
                    usage = _safe_usage(value.get("usage"))
                except (KeyError, IndexError, ValueError, TypeError) as exc:
                    raise WorkBlocked("provider returned an invalid tool envelope; no model prose was displayed") from exc
                metadata = {"response_id": str(value.get("id", ""))[:200], "requested_model": cfg.model,
                            "response_model": str(value.get("model", ""))[:180], "finish_reason": str(choice.get("finish_reason", ""))[:40],
                            "tool_names": [c["function"]["name"] for c in safe_calls], "usage": usage,
                            "response_sha256": sha256(response.content).hexdigest()}
                runtime.store.complete_call(runtime.run_id, runtime.owner, runtime.role, request_id, {"ok": True, "metadata": metadata},
                                            [{"role": runtime.role.value, "operation": Operation.PROVIDER_RESPONSE_RECEIVED,
                                              "object_kind": "provider_response", "object_id": request_id, "status": "completed", "worker_kind": "external", "parent_event":runtime.parent_event,
                                              "message": "Received tool calls and provider usage metadata", "after": metadata}])
                if usage and usage.get("cost") is not None:
                    observed_cost += Decimal(str(usage["cost"]))
                    if observed_cost > cfg.total_cost_limit:
                        raise WorkBlocked("reported provider cost exceeds the allowed limit; no more calls")
                messages.append({"role": "assistant", "content": None, "tool_calls": safe_calls})
                for item in safe_calls:
                    calls += 1
                    if calls > cfg.max_tool_calls:
                        raise WorkBlocked("model tool budget exhausted")
                    name = item["function"]["name"]
                    arguments = json.loads(item["function"]["arguments"], object_pairs_hook=_unique_pairs)
                    result = runtime.call(name, arguments, "external." + item["id"])
                    messages.append({"role": "tool", "tool_call_id": item["id"], "content": canonical(result).decode()})
                    if name == "finish_work" and result["ok"]:
                        return
            raise WorkBlocked("external facts role did not finish within its request limit")
        finally:
            if self._client is None:
                client.close()


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON member")
        result[key] = value
    return result


def _safe_usage(value):
    if not isinstance(value, dict):
        return None
    result = {}
    for key in ("prompt_tokens", "completion_tokens", "total_tokens", "cost"):
        amount = value.get(key)
        if isinstance(amount, (int, float)) and not isinstance(amount, bool) and amount >= 0:
            if not Decimal(str(amount)).is_finite() or key != "cost" and not isinstance(amount, int):
                continue
            result[key] = amount
    return result or None


from .contracts import ROLE_TOOLS
ROLE_TOOLS_FACTS = ROLE_TOOLS[Role.FACTS]
