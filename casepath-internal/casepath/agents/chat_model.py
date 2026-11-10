"""A model behind an OpenAI-compatible chat-completions API, such as a model hosted in a Databricks workspace.

The agents speak one dialect: ``respond`` and ``respond_json`` with Responses-style items (user messages with text and
image parts, the model's function calls carried forward, and ``function_call_output`` items). This client translates
them to chat messages with ``tool_calls`` and ``tool`` replies, and translates the answer back, so the agents, the
reading and the checks run unchanged on either provider. No extended thinking is requested; output is capped by
``max_output_tokens``. Tokens are never logged or stored.

Sign-in for a Databricks workspace: inside a Databricks App, the app's own service principal (``DATABRICKS_CLIENT_ID``
and ``DATABRICKS_CLIENT_SECRET``, which the platform provides) gets an OAuth token from the workspace; for a local
check, ``DATABRICKS_TOKEN``.
"""
import json
import os
import threading
import time

import httpx

from .azure_model import ModelError, ModelResult, RETRY_STATUSES, Turn, _error_code, wire_schema
from .schema import validate_result, validate_schema


def databricks_token_provider(host, env=os.environ, *, transport=None):
    if env.get("DATABRICKS_TOKEN"):
        token = env["DATABRICKS_TOKEN"]
        return lambda: token
    client_id, secret = env.get("DATABRICKS_CLIENT_ID"), env.get("DATABRICKS_CLIENT_SECRET")
    if not (client_id and secret):
        raise ModelError("identity_unavailable", "No Databricks identity: run as a Databricks App, or set DATABRICKS_TOKEN for a local check.")
    lock, cached = threading.Lock(), {"token": None, "until": 0.0}
    client = httpx.Client(timeout=30, transport=transport)

    def token():
        with lock:
            if cached["token"] and time.time() < cached["until"] - 120:
                return cached["token"]
            try:
                response = client.post(f"{host}/oidc/v1/token", data={"grant_type": "client_credentials", "scope": "all-apis"},
                                       auth=(client_id, secret))
            except httpx.HTTPError as error:
                raise ModelError("sign_in", f"The workspace sign-in could not be reached ({type(error).__name__}).") from None
            if response.status_code != 200:
                raise ModelError("sign_in", f"The workspace refused the app's sign-in ({response.status_code}).")
            body = response.json()
            cached.update(token=body["access_token"], until=time.time() + float(body.get("expires_in", 3600)))
            return cached["token"]
    return token


def _content(content):
    if isinstance(content, str):
        return content
    parts = []
    for part in content:
        if part.get("type") in {"input_text", "text", "output_text"}:
            parts.append({"type": "text", "text": part.get("text", "")})
        elif part.get("type") in {"input_image", "image_url"}:
            url = part["image_url"] if isinstance(part.get("image_url"), str) else part["image_url"]["url"]
            parts.append({"type": "image_url", "image_url": {"url": url}})
    return parts


def to_messages(instructions, items):
    """Responses-style input items → chat messages."""
    messages = [{"role": "system", "content": instructions}]
    for item in items:
        kind = item.get("type")
        if kind == "function_call":
            last = messages[-1]
            if not (last["role"] == "assistant" and "tool_calls" in last):
                if last["role"] == "assistant" and last.get("content") is not None and "tool_calls" not in last:
                    last["tool_calls"] = []
                else:
                    messages.append({"role": "assistant", "content": None, "tool_calls": []})
                    last = messages[-1]
            arguments = item.get("arguments")
            last["tool_calls"].append({"id": item["call_id"], "type": "function",
                                       "function": {"name": item["name"], "arguments": arguments if isinstance(arguments, str) else json.dumps(arguments)}})
        elif kind == "function_call_output":
            output = item.get("output")
            messages.append({"role": "tool", "tool_call_id": item["call_id"], "content": output if isinstance(output, str) else json.dumps(output)})
        elif kind == "reasoning":
            continue
        elif kind == "message" and item.get("role") == "assistant":
            text = "".join(p.get("text", "") for p in item.get("content") or [] if p.get("type") in {"output_text", "text"})
            messages.append({"role": "assistant", "content": text})
        elif item.get("role") in {"user", "system", "developer", "assistant"}:
            messages.append({"role": "system" if item["role"] == "developer" else item["role"], "content": _content(item["content"])})
    return messages


def _usage(payload):
    raw = payload.get("usage") or {}
    usage = {"input_tokens": int(raw.get("prompt_tokens") or 0), "output_tokens": int(raw.get("completion_tokens") or 0)}
    cached = (raw.get("prompt_tokens_details") or {}).get("cached_tokens") or raw.get("cache_read_input_tokens")
    if cached:
        usage["cached_tokens"] = int(cached)
    return usage


class ChatCompletionsModel:
    def __init__(self, settings, token_provider, *, transport=None, max_attempts=5, sleep=time.sleep):
        self.settings, self._token, self._sleep, self.max_attempts = settings, token_provider, sleep, max_attempts
        self.url = settings.endpoint + (settings.chat_path or "/serving-endpoints/chat/completions").replace("{model}", settings.deployment)
        self._client = httpx.Client(timeout=settings.timeout_seconds, follow_redirects=False, trust_env=settings.trust_env,
                                    verify=settings.ca_bundle or True, transport=transport)

    def __repr__(self):
        return f"ChatCompletionsModel(model={self.settings.deployment!r}, credential=<workspace>)"

    def close(self):
        self._client.close()

    def _post(self, body):
        attempt = 0
        while True:
            attempt += 1
            try:
                response = self._client.post(self.url, json=body, headers={"Authorization": "Bearer " + self._token()})
            except httpx.HTTPError as error:
                if attempt < self.max_attempts:
                    self._sleep(min(2 ** attempt, 20))
                    continue
                raise ModelError("transport", f"The model endpoint could not be reached ({type(error).__name__}).", attempt) from None
            if response.status_code in RETRY_STATUSES and attempt < self.max_attempts:
                try:
                    wait = float(response.headers.get("retry-after", 2 ** attempt))
                except ValueError:
                    wait = 2 ** attempt
                self._sleep(min(max(wait, 1), 60))
                continue
            if response.status_code != 200:
                code = _error_code(response)
                raise ModelError(f"http_{response.status_code}",
                                 f"The model endpoint answered {response.status_code}{' (' + code + ')' if code else ''}.", attempt)
            try:
                return response.json(), attempt
            except ValueError:
                raise ModelError("invalid_envelope", "The model response was not JSON.", attempt) from None

    def respond(self, *, instructions, input, tools=(), text_schema=None, effort="medium", tool_choice=None):
        body = {"model": self.settings.deployment, "messages": to_messages(instructions, input),
                "max_tokens": self.settings.max_output_tokens}
        if self.settings.reasoning:  # the call's effort is the model's reasoning effort (configured)
            body["reasoning_effort"] = effort
        else:
            body["temperature"] = 0
        if tools:
            body["tools"] = [{"type": "function", "function": {"name": t["name"], "description": t["description"],
                                                                "parameters": wire_schema(t["parameters"])}} for t in tools]
            if tool_choice:
                body["tool_choice"] = tool_choice if isinstance(tool_choice, str) else {"type": "function", "function": {"name": tool_choice["name"]}}
        if text_schema is not None:
            validate_schema(text_schema["schema"])
            body["response_format"] = {"type": "json_schema", "json_schema": {"name": text_schema["name"], "strict": True,
                                                                              "schema": wire_schema(text_schema["schema"])}}
        started = time.monotonic()
        payload, attempts = self._post(body)
        try:
            choice = payload["choices"][0]
            message = choice["message"]
        except (KeyError, TypeError, IndexError):
            raise ModelError("invalid_envelope", "The model response had no answer.", attempts) from None
        if choice.get("finish_reason") == "length":
            raise ModelError("max_output_tokens", "The model stopped before finishing its turn.", attempts)
        if message.get("refusal"):
            raise ModelError("refusal", "The model declined this turn.", attempts)
        text = message.get("content") if isinstance(message.get("content"), str) else \
            "".join(p.get("text", "") for p in message.get("content") or [] if isinstance(p, dict))
        output, calls = [], []
        if text:
            output.append({"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": text}]})
        for call in message.get("tool_calls") or []:
            raw = call.get("function", {}).get("arguments")
            try:
                arguments = json.loads(raw) if isinstance(raw, str) else raw
            except ValueError:
                arguments = None
            output.append({"type": "function_call", "call_id": call.get("id"), "name": call["function"]["name"],
                           "arguments": raw if isinstance(raw, str) else json.dumps(raw)})
            calls.append({"call_id": call.get("id"), "name": call["function"]["name"], "arguments": arguments})
        return Turn(output=output, calls=calls, text=text or "", usage=_usage(payload), response_id=str(payload.get("id", ""))[:200],
                    status="completed", attempts=attempts, seconds=round(time.monotonic() - started, 3))

    def respond_json(self, *, name, instructions, input, schema, effort="medium"):
        if getattr(self, "_json_via_tool", False):
            return self._json_via_tool_call(name, instructions, input, schema, effort)
        try:
            turn = self.respond(instructions=instructions, input=input, text_schema={"name": name, "schema": schema}, effort=effort)
        except ModelError as error:
            if error.reason != "http_400":
                raise
            self._json_via_tool = True  # this endpoint takes no response_format: ask for the answer as a forced tool call
            return self._json_via_tool_call(name, instructions, input, schema, effort)
        text = turn.text.strip()
        if text.startswith("```"):  # some models fence their JSON
            text = text.strip("`").split("\n", 1)[-1].rsplit("```", 1)[0]
        try:
            value = json.loads(text)
            validate_result(value, schema)
        except ValueError as error:
            raise ModelError("schema_mismatch", f"The model answer did not match its schema: {error}", turn.attempts) from None
        return ModelResult(value=value, usage=turn.usage, deployment=self.settings.deployment, response_id=turn.response_id,
                           attempts=turn.attempts, seconds=turn.seconds)

    def _json_via_tool_call(self, name, instructions, input, schema, effort):
        validate_schema(schema)
        tool = {"name": name, "description": "Give your answer as this function's arguments.", "parameters": schema}
        turn = self.respond(instructions=instructions, input=input, tools=[tool], tool_choice={"type": "function", "name": name}, effort=effort)
        call = next((c for c in turn.calls if c["name"] == name), None)
        try:
            if call is None or call["arguments"] is None:
                raise ValueError("no answer")
            validate_result(call["arguments"], schema)
        except ValueError as error:
            raise ModelError("schema_mismatch", f"The model answer did not match its schema: {error}", turn.attempts) from None
        return ModelResult(value=call["arguments"], usage=turn.usage, deployment=self.settings.deployment, response_id=turn.response_id,
                           attempts=turn.attempts, seconds=turn.seconds)
