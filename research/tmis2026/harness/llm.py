"""Minimal OpenRouter client for the TMIS experiments.

Every call is cached on disk by a hash of (request body, run index), so a
repeated run never pays twice, and every attempt is appended to a ledger with
tokens, cost and latency. A hard budget cap refuses new calls once reached.
The API key is injected by the session proxy; nothing secret is stored here.
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
MODEL = os.environ.get("TMIS_MODEL", "openai/gpt-6.1-terra")
RUNS = Path(__file__).resolve().parents[1] / "runs"
CACHE = RUNS / "cache"
LEDGER = RUNS / "ledger.jsonl"
BUDGET_USD = float(os.environ.get("TMIS_BUDGET_USD", "40"))
_lock = threading.Lock()


class BudgetExceeded(RuntimeError):
    pass


def spent() -> float:
    if not LEDGER.exists():
        return 0.0
    total = 0.0
    for line in LEDGER.read_text().splitlines():
        row = json.loads(line)
        total += float(row.get("cost") or 0.0)
    return total


def _key(body: dict, run: int) -> str:
    raw = json.dumps({"body": body, "run": run}, sort_keys=True, ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()


def call(*, system: str, user: str, schema: dict, schema_name: str, run: int, tag: dict,
         max_tokens: int = 3500, effort: str = "low", model: str = MODEL) -> dict:
    """Return {'result': parsed JSON or None, 'usage':..., 'cached': bool, 'error': str|None}."""
    body = {"model": model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "response_format": {"type": "json_schema",
                                "json_schema": {"name": schema_name, "strict": True, "schema": schema}},
            "max_tokens": max_tokens, "reasoning": {"effort": effort, "exclude": True},
            "usage": {"include": True},
            "provider": {"allow_fallbacks": False, "require_parameters": True, "data_collection": "deny"}}
    key = _key(body, run)
    path = CACHE / key[:2] / f"{key}.json"
    if path.exists():
        saved = json.loads(path.read_text())
        return {**saved, "cached": True}
    with _lock:
        if spent() >= BUDGET_USD:
            raise BudgetExceeded(f"budget {BUDGET_USD} USD reached")
    data = json.dumps(body, ensure_ascii=False).encode()
    error, response, latency = None, None, None
    for attempt in range(4):
        start = time.time()
        req = urllib.request.Request(ENDPOINT, data=data, method="POST", headers={
            "Authorization": "Bearer proxy-injected", "Content-Type": "application/json",
            "X-Title": "CasePath TMIS experiments"})
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                response = json.loads(r.read())
            latency = time.time() - start
            error = None
            break
        except urllib.error.HTTPError as exc:
            error = f"http {exc.code}: {exc.read()[:300]!r}"
            if exc.code not in (429, 500, 502, 503, 504):
                break
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            error = f"{type(exc).__name__}: {exc}"
        time.sleep(2 ** (attempt + 1))
    usage = (response or {}).get("usage") or {}
    result, finish = None, None
    if response and response.get("choices"):
        choice = response["choices"][0]
        finish = choice.get("finish_reason")
        content = (choice.get("message") or {}).get("content")
        try:
            result = json.loads(content) if content else None
        except json.JSONDecodeError:
            error = "invalid JSON content"
        if finish != "stop" and error is None:
            error = f"finish_reason={finish}"
    elif response is not None and error is None:
        error = f"no choices: {json.dumps(response)[:300]}"
    record = {"result": result, "error": error, "finish_reason": finish, "usage": usage,
              "latency_s": latency, "model": (response or {}).get("model"),
              "provider": (response or {}).get("provider"), "tag": tag, "run": run}
    with _lock:
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with LEDGER.open("a") as fh:
            fh.write(json.dumps({"time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "key": key,
                                 "tag": tag, "run": run, "model": record["model"], "provider": record["provider"],
                                 "prompt_tokens": usage.get("prompt_tokens"),
                                 "cached_tokens": (usage.get("prompt_tokens_details") or {}).get("cached_tokens"),
                                 "completion_tokens": usage.get("completion_tokens"),
                                 "reasoning_tokens": (usage.get("completion_tokens_details") or {}).get("reasoning_tokens"),
                                 "cost": usage.get("cost"), "latency_s": latency, "error": error}) + "\n")
        if result is not None or (error and not error.startswith(("http 429", "http 5", "URLError", "TimeoutError"))):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(record, ensure_ascii=False))
    return {**record, "cached": False}
