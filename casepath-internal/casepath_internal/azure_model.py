"""Direct Azure OpenAI client: Entra sign-in, exact deployment, strict JSON output.

The client calls ``{endpoint}/openai/v1/chat/completions`` with the configured
deployment name. It authenticates with an Entra bearer token from the runtime's
own identity (developer sign-in in a workspace, managed identity in a service).
There are no API keys, provider headers, model catalogues or price tables.
Tokens are never logged or stored.
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


def entra_token_provider(scope=SCOPE):
    """Return a callable giving a fresh bearer token from the runtime identity."""
    try:
        from azure.identity import DefaultAzureCredential, get_bearer_token_provider
    except ImportError as error:
        raise ModelError("identity_unavailable", "Install azure-identity in the internal runtime to sign in with Entra.") from error
    return get_bearer_token_provider(DefaultAzureCredential(exclude_interactive_browser_credential=True), scope)


class AzureOpenAIModel:
    def __init__(self, settings, token_provider, *, transport=None, max_attempts=3, sleep=time.sleep):
        self.settings, self._token, self._sleep = settings, token_provider, sleep
        self.max_attempts = max_attempts
        verify = settings.ca_bundle or True
        self._client = httpx.Client(timeout=settings.timeout_seconds, follow_redirects=False,
                                    trust_env=settings.trust_env, verify=verify, transport=transport)
        self.url = settings.endpoint + "/openai/v1/chat/completions"

    def __repr__(self):
        return f"AzureOpenAIModel(deployment={self.settings.deployment!r}, credential=<entra>)"

    def close(self):
        self._client.close()

    def request_body(self, name, system, user, schema):
        validate_schema(schema)
        body = {"model": self.settings.deployment,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                "response_format": {"type": "json_schema", "json_schema": {"name": name, "strict": True, "schema": wire_schema(schema)}},
                "max_completion_tokens": self.settings.max_output_tokens}
        if self.settings.reasoning:
            body["reasoning_effort"] = "low"
        else:
            body["temperature"] = 0
        return body

    def complete_json(self, *, name, system, user, schema):
        body = self.request_body(name, system, user, schema)
        started, attempt = time.monotonic(), 0
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
                self._sleep(min(max(wait, 1), 30))
                continue
            break
        if response.status_code != 200:
            code = _error_code(response)
            raise ModelError(f"http_{response.status_code}", f"The model endpoint answered {response.status_code}{' (' + code + ')' if code else ''}.", attempt)
        try:
            payload = response.json()
            choice, = payload["choices"]
            message = choice["message"]
        except (ValueError, KeyError, TypeError):
            raise ModelError("invalid_envelope", "The model response was not a single chat completion.", attempt) from None
        if choice.get("finish_reason") != "stop":
            raise ModelError(str(choice.get("finish_reason") or "incomplete"), "The model stopped before finishing its answer.", attempt)
        if message.get("refusal") or not isinstance(message.get("content"), str):
            raise ModelError("refusal", "The model declined or returned no structured answer.", attempt)
        try:
            value = json.loads(message["content"])
            validate_result(value, schema)
        except ValueError as error:
            raise ModelError("schema_mismatch", f"The model answer did not match its schema: {error}", attempt) from None
        usage = {k: v for k, v in (payload.get("usage") or {}).items()
                 if k in {"prompt_tokens", "completion_tokens", "total_tokens"} and type(v) is int}
        return ModelResult(value=value, usage=usage, deployment=self.settings.deployment,
                           response_id=str(payload.get("id", ""))[:200], attempts=attempt,
                           seconds=round(time.monotonic() - started, 3))


def wire_schema(schema):
    """Keep the keywords every strict-mode deployment accepts; bounds are enforced locally."""
    kept = {k: v for k, v in schema.items() if k in {"type", "required", "additionalProperties", "enum", "const", "description"}}
    if "properties" in schema:
        kept["properties"] = {k: wire_schema(v) for k, v in schema["properties"].items()}
    if "items" in schema:
        kept["items"] = wire_schema(schema["items"])
    return kept


def _error_code(response):
    try:
        error = response.json().get("error") or {}
        return str(error.get("code") or "")[:80]
    except (ValueError, AttributeError):
        return ""
