"""OpenRouter chat-completions transport for arena arms (one physical call per request directory).

The key is read from the file named by CASEPATH_OPENROUTER_KEY_FILE and is never logged. Every call
writes answer.json (the model content) and receipt.json (usage, reported cost, model, latency, attempts).
Transport-level failures (connection errors, 5xx, 429) are retried at most twice with backoff and
recorded; model-output failures are never retried.
"""
from __future__ import annotations

import hashlib, json, os, time
from pathlib import Path
from typing import Any

import httpx

ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"


def _api_key() -> str:
    path = os.environ.get("CASEPATH_OPENROUTER_KEY_FILE")
    if not path:
        raise RuntimeError("CASEPATH_OPENROUTER_KEY_FILE is not set")
    value = Path(path).read_text("utf-8").strip()
    if len(value) < 20 or any(c.isspace() for c in value):
        raise RuntimeError("malformed key file")
    return value


def call_once(messages: list[dict[str, str]], *, model: str, max_tokens: int, temperature: float, provider_only: list[str] | None, timeout: float = 240.0) -> dict[str, Any]:
    payload: dict[str, Any] = {"model": model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens,
                               "response_format": {"type": "json_object"}, "usage": {"include": True}}
    if provider_only:
        payload["provider"] = {"only": provider_only, "allow_fallbacks": False}
    headers = {"Authorization": "Bearer " + _api_key(), "Content-Type": "application/json", "HTTP-Referer": "https://casepath.local/arena-v1", "X-Title": "CasePath arena v1"}
    started = time.time()
    with httpx.Client(timeout=timeout) as client:
        response = client.post(ENDPOINT, headers=headers, json=payload)
    latency = time.time() - started
    if response.status_code != 200:
        return {"ok": False, "status": response.status_code, "error": response.text[:2000], "latency_s": latency}
    body = response.json()
    try:
        content = body["choices"][0]["message"]["content"]
        finish = body["choices"][0].get("finish_reason")
    except (KeyError, IndexError, TypeError):
        return {"ok": False, "status": 200, "error": "malformed completion body", "latency_s": latency, "body": body}
    usage = body.get("usage", {})
    return {"ok": True, "content": content, "finish_reason": finish, "model": body.get("model"), "generation_id": body.get("id"),
            "provider": body.get("provider"), "usage": usage, "cost_usd": usage.get("cost"), "latency_s": latency,
            "payload_sha256": hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()}


def call_with_transport_retry(messages, **kw) -> dict[str, Any]:
    attempts = []
    for attempt in range(3):
        try:
            result = call_once(messages, **kw)
        except (httpx.HTTPError, OSError) as exc:
            result = {"ok": False, "status": None, "error": f"{type(exc).__name__}: {exc}"[:500], "latency_s": None}
        attempts.append({k: result.get(k) for k in ("ok", "status", "error", "latency_s")})
        if result["ok"]:
            result["attempts"] = attempts; return result
        if result.get("status") is not None and result["status"] < 500 and result["status"] != 429:
            break
        time.sleep(3 * (attempt + 1))
    result["attempts"] = attempts
    return result
