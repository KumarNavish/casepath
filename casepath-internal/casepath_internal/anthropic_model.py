"""A workspace model behind the Messages API (the native API of the model family a gateway may host).

Some gateways refuse forced tool calls and structured output on their OpenAI-compatible routes but pass them on the
model's native Messages API. This client translates the agents' dialect (Responses-style items: user messages with
text and image parts, the model's function calls carried forward, ``function_call_output`` items) to messages with
``tool_use`` and ``tool_result`` blocks and back. A structured answer is a tool call whose input is the answer.
Where the gateway refuses forced tool choice, only the tool that must be called is offered and the instructions say
so; a structured answer is then checked and asked for once more if it is missing or malformed. The system prompt, the tool list and the conversation so far are marked for prompt caching, so a long agent
loop pays for its repeated prefix only once; a gateway that refuses the marks gets the same request without them.
"""
import json
import time

import httpx

from .azure_model import ModelError, ModelResult, RETRY_STATUSES, Turn, _error_code, wire_schema
from .schema import validate_result, validate_schema

CACHE = {"type": "ephemeral"}


def _image(url):
    header, _, data = url.partition(",")
    media = header[5:].split(";")[0] if header.startswith("data:") else "image/png"
    return {"type": "image", "source": {"type": "base64", "media_type": media, "data": data}}


def _blocks(content):
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    blocks = []
    for part in content:
        if part.get("type") in {"input_text", "text", "output_text"}:
            blocks.append({"type": "text", "text": part.get("text", "")})
        elif part.get("type") in {"input_image", "image_url"}:
            blocks.append(_image(part["image_url"] if isinstance(part["image_url"], str) else part["image_url"]["url"]))
    return blocks


def to_messages(items):
    """Responses-style input items → alternating user and assistant messages with content blocks."""
    messages = []

    def add(role, blocks):
        if messages and messages[-1]["role"] == role:
            messages[-1]["content"].extend(blocks)
        else:
            messages.append({"role": role, "content": list(blocks)})
    for item in items:
        kind = item.get("type")
        if kind == "function_call":
            arguments = item.get("arguments")
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments)
                except ValueError:
                    arguments = {}
            add("assistant", [{"type": "tool_use", "id": item["call_id"], "name": item["name"], "input": arguments or {}}])
        elif kind == "function_call_output":
            output = item.get("output")
            add("user", [{"type": "tool_result", "tool_use_id": item["call_id"], "content": output if isinstance(output, str) else json.dumps(output)}])
        elif kind == "reasoning":
            continue
        elif kind == "message" and item.get("role") == "assistant":
            text = "".join(p.get("text", "") for p in item.get("content") or [] if p.get("type") in {"output_text", "text"})
            if text:
                add("assistant", [{"type": "text", "text": text}])
        elif item.get("role") in {"user", "system", "developer"}:
            add("user", _blocks(item["content"]))
        elif item.get("role") == "assistant":
            add("assistant", _blocks(item["content"]))
    return messages


def _usage(payload):
    raw = payload.get("usage") or {}
    cached, created = int(raw.get("cache_read_input_tokens") or 0), int(raw.get("cache_creation_input_tokens") or 0)
    usage = {"input_tokens": int(raw.get("input_tokens") or 0) + cached + created, "output_tokens": int(raw.get("output_tokens") or 0)}
    if cached:
        usage["cached_tokens"] = cached  # read from the cache; included in input_tokens
    if created:
        usage["cache_write_tokens"] = created  # written to the cache; included in input_tokens
    return usage


class AnthropicMessagesModel:
    def __init__(self, settings, token_provider, *, transport=None, max_attempts=5, sleep=time.sleep):
        self.settings, self._token, self._sleep, self.max_attempts = settings, token_provider, sleep, max_attempts
        self.url = settings.endpoint + (settings.chat_path or "/ai-gateway/anthropic/v1/messages")
        self.cache = True
        self.forced = getattr(settings, "forced_tools", True)  # False where the gateway refuses tool_choice "tool"/"any"
        self._client = httpx.Client(timeout=settings.timeout_seconds, follow_redirects=False, trust_env=settings.trust_env,
                                    verify=settings.ca_bundle or True, transport=transport)

    def __repr__(self):
        return f"AnthropicMessagesModel(model={self.settings.deployment!r}, credential=<workspace>)"

    def close(self):
        self._client.close()

    def _post(self, body):
        attempt = 0
        while True:
            attempt += 1
            try:
                response = self._client.post(self.url, json=body, headers={"Authorization": "Bearer " + self._token(),
                                                                           "anthropic-version": "2023-06-01"})
            except httpx.HTTPError as error:
                if attempt < self.max_attempts:
                    self._sleep(min(2 ** attempt, 20))
                    continue
                raise ModelError("transport", f"The model endpoint could not be reached ({type(error).__name__}).", attempt) from None
            if response.status_code in RETRY_STATUSES | {529} and attempt < self.max_attempts:
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

    def _body(self, instructions, input, tools, tool_choice, mark_last=True):
        messages = to_messages(input)
        system = instructions
        if tools and tool_choice and not self.forced:
            # Without forced tool choice: offer only the tool that must be called, and say so; otherwise ask for tools.
            if isinstance(tool_choice, dict):
                tools = [t for t in tools if t["name"] == tool_choice["name"]] or tools
                system += f"\n\nRespond only by calling the {tool_choice['name']} tool."
            elif tool_choice == "required":
                system += "\n\nAct only through your tools: every answer is a tool call, never plain text."
            tool_choice = None
        body = {"model": self.settings.deployment, "max_tokens": self.settings.max_output_tokens,
                "system": [{"type": "text", "text": system}], "messages": messages}
        if tools:
            body["tools"] = [{"name": t["name"], "description": t["description"], "input_schema": wire_schema(t["parameters"])} for t in tools]
            if tool_choice:
                body["tool_choice"] = {"type": "any"} if tool_choice == "required" else {"type": "auto"} if tool_choice == "auto" else \
                    {"type": "tool", "name": tool_choice["name"]}
        if self.cache:
            body["system"][-1]["cache_control"] = CACHE
            if tools:
                body["tools"][-1]["cache_control"] = CACHE
            # An agent's next turn repeats this whole conversation, so its end is worth caching; a one-off structured
            # answer is not repeated, and a cache write nobody reads costs more than no cache.
            if mark_last and messages and messages[-1]["content"]:
                messages[-1]["content"][-1] = {**messages[-1]["content"][-1], "cache_control": CACHE}
        return body

    def respond(self, *, instructions, input, tools=(), text_schema=None, effort="medium", tool_choice=None):
        if text_schema is not None:  # a structured answer is a forced tool call
            tools, tool_choice = [{"name": text_schema["name"], "description": "Give your answer as this tool's input.",
                                   "parameters": text_schema["schema"]}], {"type": "function", "name": text_schema["name"]}
        started, mark_last = time.monotonic(), text_schema is None
        try:
            payload, attempts = self._post(self._body(instructions, input, tools, tool_choice, mark_last))
        except ModelError as error:
            if error.reason != "http_400" or not self.cache:
                raise
            # Try once without cache marks; only if that succeeds were the marks the problem, and they stay off.
            self.cache = False
            try:
                payload, attempts = self._post(self._body(instructions, input, tools, tool_choice, mark_last))
            except ModelError:
                self.cache = True
                raise
        if payload.get("stop_reason") == "max_tokens":
            raise ModelError("max_output_tokens", "The model stopped before finishing its turn.", attempts)
        output, calls, texts = [], [], []
        for block in payload.get("content") or []:
            if block.get("type") == "text" and block.get("text"):
                texts.append(block["text"])
                output.append({"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": block["text"]}]})
            elif block.get("type") == "tool_use":
                output.append({"type": "function_call", "call_id": block["id"], "name": block["name"], "arguments": json.dumps(block.get("input") or {})})
                calls.append({"call_id": block["id"], "name": block["name"], "arguments": block.get("input")})
        return Turn(output=output, calls=calls, text="".join(texts), usage=_usage(payload), response_id=str(payload.get("id", ""))[:200],
                    status="completed", attempts=attempts, seconds=round(time.monotonic() - started, 3))

    def respond_json(self, *, name, instructions, input, schema, effort="medium"):
        validate_schema(schema)
        conversation, usage, problem = list(input), {}, "no answer"
        for attempt in range(2):  # one more try, with the problem named, when the answer is missing or malformed
            turn = self.respond(instructions=instructions, input=conversation, text_schema={"name": name, "schema": schema}, effort=effort)
            usage = {k: usage.get(k, 0) + v for k, v in turn.usage.items()}
            call = next((c for c in turn.calls if c["name"] == name), None)
            value = call["arguments"] if call else _json_text(turn.text)
            try:
                if not isinstance(value, dict):
                    raise ValueError("no answer")
                validate_result(value, schema)
                return ModelResult(value=value, usage=usage, deployment=self.settings.deployment, response_id=turn.response_id,
                                   attempts=turn.attempts, seconds=turn.seconds)
            except ValueError as error:
                problem = str(error)
            conversation = list(input) + [{"role": "user", "content": f"Answer again by calling the {name} tool; the last answer had a problem: {problem}"}]
        raise ModelError("schema_mismatch", f"The model answer did not match its schema: {problem}", turn.attempts)


def _json_text(text):
    """A JSON object written as text instead of a tool call, if that is what came back."""
    text = (text or "").strip()
    if text.startswith("```"):
        text = text.strip("`").split("\n", 1)[-1].rsplit("```", 1)[0]
    start, end = text.find("{"), text.rfind("}")
    try:
        return json.loads(text[start:end + 1]) if start >= 0 < end else None
    except ValueError:
        return None
