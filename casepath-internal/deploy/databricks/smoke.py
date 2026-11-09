"""Check what a workspace model supports before CasePath depends on it: about a dozen tiny calls, no case data.

In a Databricks notebook cell (standard library only, nothing to install):

    exec(open("/Workspace/Users/<you>/casepath-app/deploy/databricks/smoke.py").read())   # or paste this file
    ctx = dbutils.notebook.entry_point.getDbutils().notebook().getContext()
    check(ctx.apiUrl().get(), ctx.apiToken().get(), "<the model's full name from its Use panel>")

It tries each feature the agents use (plain answer, forced tool call, structured JSON answer, page image) through the
gateway's chat-completions and responses routes, and prints one content-free line per check with its token count.
"""
import base64
import json
import struct
import urllib.error
import urllib.request
import zlib


def _png():
    """A 16 x 16 red square."""
    rows = b"".join(b"\x00" + b"\xff\x00\x00" * 16 for _ in range(16))
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xffffffff)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 16, 16, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b"")


IMAGE = "data:image/png;base64," + base64.b64encode(_png()).decode()
TOOL = {"name": "record", "description": "Record a colour.", "parameters": {"type": "object", "properties": {"colour": {"type": "string"}},
                                                                            "required": ["colour"], "additionalProperties": False}}
SCHEMA = {"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"], "additionalProperties": False}


def _post(url, token, body):
    request = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                     headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as error:
        try:
            detail = json.loads(error.read()).get("error", {})
            detail = detail.get("code") or detail.get("message", "")[:80] if isinstance(detail, dict) else str(detail)[:80]
        except ValueError:
            detail = ""
        return error.code, {"error": detail}


def check(host, token, model, base="/ai-gateway/mlflow/v1"):
    host = host.rstrip("/")
    chat, responses = f"{host}{base}/chat/completions", f"{host}{base}/responses"
    say = {"role": "user", "content": "Say OK."}
    see = {"role": "user", "content": [{"type": "text", "text": "Which colour is this square? One word."},
                                       {"type": "image_url", "image_url": {"url": IMAGE}}]}
    cases = [
        ("chat text", chat, {"messages": [say], "max_tokens": 16},
         lambda r: bool(r["choices"][0]["message"].get("content"))),
        ("chat forced tool", chat, {"messages": [{"role": "user", "content": "The colour is red. Record it."}], "max_tokens": 128,
                                    "tools": [{"type": "function", "function": TOOL}], "tool_choice": {"type": "function", "function": {"name": "record"}}},
         lambda r: r["choices"][0]["message"]["tool_calls"][0]["function"]["name"] == "record"),
        ("chat json schema", chat, {"messages": [{"role": "user", "content": "Answer ok=true."}], "max_tokens": 64,
                                    "response_format": {"type": "json_schema", "json_schema": {"name": "check", "strict": True, "schema": SCHEMA}}},
         lambda r: json.loads(r["choices"][0]["message"]["content"])["ok"] is True),
        ("chat image", chat, {"messages": [see], "max_tokens": 16},
         lambda r: "red" in (r["choices"][0]["message"].get("content") or "").lower()),
        ("responses text", responses, {"input": [{"role": "user", "content": [{"type": "input_text", "text": "Say OK."}]}], "max_output_tokens": 16},
         lambda r: any(i.get("type") == "message" for i in r.get("output", []))),
        ("responses forced tool", responses, {"input": [{"role": "user", "content": [{"type": "input_text", "text": "The colour is red. Record it."}]}],
                                              "max_output_tokens": 128, "tools": [{"type": "function", **TOOL}],
                                              "tool_choice": {"type": "function", "name": "record"}},
         lambda r: any(i.get("type") == "function_call" for i in r.get("output", []))),
        ("responses json schema", responses, {"input": [{"role": "user", "content": [{"type": "input_text", "text": "Answer ok=true."}]}],
                                              "max_output_tokens": 64, "text": {"format": {"type": "json_schema", "name": "check", "strict": True, "schema": SCHEMA}}},
         lambda r: any(i.get("type") == "message" for i in r.get("output", []))),
        ("responses image", responses, {"input": [{"role": "user", "content": [{"type": "input_text", "text": "Which colour is this square? One word."},
                                                                               {"type": "input_image", "image_url": IMAGE}]}], "max_output_tokens": 16},
         lambda r: "red" in json.dumps(r.get("output", [])).lower()),
    ]
    total = 0
    for name, url, body, ok in cases:
        status, reply = _post(url, token, {"model": model, **body})
        usage = reply.get("usage") or {}
        tokens = sum(v for k, v in usage.items() if k in {"prompt_tokens", "completion_tokens", "input_tokens", "output_tokens"} and isinstance(v, int))
        total += tokens
        try:
            verdict = "works" if status == 200 and ok(reply) else f"no ({status} {reply.get('error', '')})".strip()
        except (KeyError, IndexError, TypeError, ValueError):
            verdict = f"no ({status}, unexpected answer shape)"
        print(f"{name:24} {verdict:40} {tokens} tokens")
    print(f"{'total':24} {'':40} {total} tokens")
