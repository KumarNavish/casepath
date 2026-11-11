"""Part C, step 1: one tiny chat request asking for three completions (n: 3) with the settings the readings use
(reasoning_effort "low", structured output json_schema strict, max_tokens), through the harness transport (cost row in
the development ledger, arm SPEED-n3-test). Prints the status, the number of choices, the usage and any error body.

    <venv>/bin/python harness/speed/n3_test.py
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parents[0] / "product"), str(HERE)]
import httpx  # noqa: E402
import transport as tp  # noqa: E402

schema = {"type": "object", "additionalProperties": False, "required": ["colour"], "properties": {"colour": {"type": "string"}}}
body = {"model": "gpt-6-luna", "max_tokens": 200, "reasoning_effort": "low", "n": 3,
        "messages": [{"role": "system", "content": "Answer in JSON."}, {"role": "user", "content": "Name one colour, any colour."}],
        "response_format": {"type": "json_schema", "json_schema": {"name": "casepath_n3_test", "strict": True, "schema": schema}}}
if "--require-parameters" in sys.argv:  # ask the router to use only providers that honour every parameter
    body["provider"] = {"require_parameters": True}
t = tp.LiveTransport("gpt-6-luna", 9001, "n3-test", arm="SPEED-n3-test")
client = httpx.Client(transport=t, timeout=120)
r = client.post("https://openrouter.ai/api/v1/chat/completions", json=body, headers={"Authorization": "Bearer proxy-injected"})
print("status", r.status_code)
try:
    payload = r.json()
except ValueError:
    print(r.text[:2000])
    raise SystemExit
print("choices", len(payload.get("choices") or []))
for c in payload.get("choices") or []:
    print(" ", c.get("index"), c.get("finish_reason"), (c.get("message") or {}).get("content"))
print("usage", json.dumps(payload.get("usage")))
print("provider", payload.get("provider"), "model", payload.get("model"))
if "error" in payload:
    print("error", json.dumps(payload["error"])[:2000])
print("calls", json.dumps(t.report()["calls"]))
