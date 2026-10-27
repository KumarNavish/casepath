"""Direct Azure OpenAI client: Entra sign-in, exact deployment, strict JSON output.

The client calls ``{endpoint}/openai/v1/responses`` (the agent loop, with tools)
and ``{endpoint}/openai/v1/chat/completions`` (single structured answers, for
deployments without the Responses API). It authenticates with an Entra bearer
token from the runtime's own identity: developer sign-in in a workspace,
managed identity in a service. There are no API keys, provider headers, model
catalogues or price tables. Responses are requested with ``store: false`` so
the service keeps no copy; reasoning is carried between turns as encrypted
items. Tokens are never logged or stored.
"""
from dataclasses import dataclass
import json
import time

import httpx

from .schema import validate_result, validate_schema

SCOPE = "https://cognitiveservices.azure.com/.default"
RETRY_STATUSES = {408, 429, 500, 502, 503, 504}


class ModelError(RuntimeError):
    def __init__(self, reason, message, attempts=0):
        super().__init__(message)
        self.reason, self.attempts = reason, attempts


@dataclass(frozen=True)
class ModelResult:
    value: dict
    usage: dict
    deployment: str
    response_id: str
    attempts: int
    seconds: float


@dataclass(frozen=True)
class Turn:
    """One Responses API turn: the items to carry forward and what they ask for."""
    output: list
    calls: list
    text: str
    usage: dict
    response_id: str
    status: str
    attempts: int
    seconds: float


def entra_token_provider(scope=SCOPE):
    """Return a callable giving a fresh bearer token from the runtime identity.

    The person's `az` sign-in comes first (Cloud Shell, a development workspace),
    then a managed identity (an operated service). Azure's default chain tries the
    managed identity first, which in Cloud Shell can time out before `az` is tried.
    """
    try:
        from azure.identity import AzureCliCredential, ChainedTokenCredential, ManagedIdentityCredential, get_bearer_token_provider
    except ImportError as error:
        raise ModelError("identity_unavailable", "Install azure-identity in the internal runtime to sign in with Entra.") from error
    return get_bearer_token_provider(ChainedTokenCredential(AzureCliCredential(), ManagedIdentityCredential()), scope)


def wire_schema(schema):
    """Keep the keywords every strict-mode deployment accepts; bounds are enforced locally."""
    kept = {k: v for k, v in schema.items() if k in {"type", "required", "additionalProperties", "enum", "const", "description"}}
    if "properties" in schema:
        kept["properties"] = {k: wire_schema(v) for k, v in schema["properties"].items()}
    if "items" in schema:
        kept["items"] = wire_schema(schema["items"])
    return kept


def _usage(payload):
    raw = payload.get("usage") or {}
    keep = {"prompt_tokens", "completion_tokens", "total_tokens", "input_tokens", "output_tokens"}
    usage = {k: v for k, v in raw.items() if k in keep and type(v) is int}
    reasoning = (raw.get("output_tokens_details") or {}).get("reasoning_tokens")
    if type(reasoning) is int:
        usage["reasoning_tokens"] = reasoning
    return usage


class AzureOpenAIModel:
    def __init__(self, settings, token_provider, *, transport=None, max_attempts=5, sleep=time.sleep):
        self.settings, self._token, self._sleep = settings, token_provider, sleep
        self.max_attempts = max_attempts
        self._client = httpx.Client(timeout=settings.timeout_seconds, follow_redirects=False,
                                    trust_env=settings.trust_env, verify=settings.ca_bundle or True, transport=transport)
        self.base = settings.endpoint + "/openai/v1"

    def __repr__(self):
        return f"AzureOpenAIModel(deployment={self.settings.deployment!r}, credential=<entra>)"

    def close(self):
        self._client.close()

    def _post(self, path, body):
        attempt = 0
        while True:
            attempt += 1
            try:
                response = self._client.post(self.base + path, json=body, headers={"Authorization": "Bearer " + self._token()})
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
                self._sleep(min(max(wait, 1), 30))
                continue
            if response.status_code != 200:
                code = _error_code(response)
                raise ModelError(f"http_{response.status_code}",
                                 f"The model endpoint answered {response.status_code}{' (' + code + ')' if code else ''}.", attempt)
            try:
                return response.json(), attempt
            except ValueError:
                raise ModelError("invalid_envelope", "The model response was not JSON.", attempt) from None

    # Responses API: the agent loop.
    def respond(self, *, instructions, input, tools=(), text_schema=None, effort="medium"):
        body = {"model": self.settings.deployment, "instructions": instructions, "input": list(input),
                "store": False, "max_output_tokens": self.settings.max_output_tokens}
        if tools:
            body["tools"] = [{"type": "function", "name": t["name"], "description": t["description"],
                              "parameters": wire_schema(t["parameters"]), "strict": True} for t in tools]
            body["parallel_tool_calls"] = True
        if text_schema is not None:
            validate_schema(text_schema["schema"])
            body["text"] = {"format": {"type": "json_schema", "name": text_schema["name"], "strict": True,
                                       "schema": wire_schema(text_schema["schema"])}}
        if self.settings.reasoning:
            body["reasoning"] = {"effort": effort}
            body["include"] = ["reasoning.encrypted_content"]
        else:
            body["temperature"] = 0
        started = time.monotonic()
        payload, attempts = self._post("/responses", body)
        output = payload.get("output")
        if not isinstance(output, list):
            raise ModelError("invalid_envelope", "The response has no output items.", attempts)
        status = str(payload.get("status") or "")
        if status not in {"completed", "incomplete"}:
            raise ModelError(status or "failed", "The model did not complete its turn.", attempts)
        if status == "incomplete":
            reason = (payload.get("incomplete_details") or {}).get("reason") or "incomplete"
            raise ModelError(str(reason), "The model stopped before finishing its turn.", attempts)
        calls, texts = [], []
        for item in output:
            kind = item.get("type") if isinstance(item, dict) else None
            if kind == "function_call":
                try:
                    arguments = json.loads(item["arguments"])
                except (KeyError, TypeError, ValueError):
                    arguments = None
                calls.append({"call_id": item.get("call_id"), "name": item.get("name"), "arguments": arguments})
            elif kind == "message":
                for part in item.get("content") or []:
                    if part.get("type") == "refusal":
                        raise ModelError("refusal", "The model declined this turn.", attempts)
                    if part.get("type") == "output_text":
                        texts.append(part.get("text") or "")
        return Turn(output=output, calls=calls, text="".join(texts), usage=_usage(payload),
                    response_id=str(payload.get("id", ""))[:200], status=status, attempts=attempts,
                    seconds=round(time.monotonic() - started, 3))

    def respond_json(self, *, name, instructions, input, schema, effort="medium"):
        turn = self.respond(instructions=instructions, input=input, text_schema={"name": name, "schema": schema}, effort=effort)
        try:
            value = json.loads(turn.text)
            validate_result(value, schema)
        except ValueError as error:
            raise ModelError("schema_mismatch", f"The model answer did not match its schema: {error}", turn.attempts) from None
        return ModelResult(value=value, usage=turn.usage, deployment=self.settings.deployment,
                           response_id=turn.response_id, attempts=turn.attempts, seconds=turn.seconds)

    # Chat completions: single structured answers on deployments without Responses.
    def complete_json(self, *, name, system, user, schema):
        validate_schema(schema)
        body = {"model": self.settings.deployment,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                "response_format": {"type": "json_schema", "json_schema": {"name": name, "strict": True, "schema": wire_schema(schema)}},
                "max_completion_tokens": self.settings.max_output_tokens}
        if self.settings.reasoning:
            body["reasoning_effort"] = "low"
        else:
            body["temperature"] = 0
        started = time.monotonic()
        payload, attempts = self._post("/chat/completions", body)
        try:
            choice, = payload["choices"]
            message = choice["message"]
        except (KeyError, TypeError, ValueError):
            raise ModelError("invalid_envelope", "The model response was not a single chat completion.", attempts) from None
        if choice.get("finish_reason") != "stop":
            raise ModelError(str(choice.get("finish_reason") or "incomplete"), "The model stopped before finishing its answer.", attempts)
        if message.get("refusal") or not isinstance(message.get("content"), str):
            raise ModelError("refusal", "The model declined or returned no structured answer.", attempts)
        try:
            value = json.loads(message["content"])
            validate_result(value, schema)
        except ValueError as error:
            raise ModelError("schema_mismatch", f"The model answer did not match its schema: {error}", attempts) from None
        return ModelResult(value=value, usage=_usage(payload), deployment=self.settings.deployment,
                           response_id=str(payload.get("id", ""))[:200], attempts=attempts,
                           seconds=round(time.monotonic() - started, 3))


def _error_code(response):
    try:
        error = response.json().get("error") or {}
        return str(error.get("code") or "")[:80]
    except (ValueError, AttributeError):
        return ""
