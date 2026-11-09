import json
import unittest

import httpx

from casepath_internal.chat_model import ChatCompletionsModel, databricks_token_provider, to_messages
from casepath_internal.config import SettingsError, load_settings

HOST = "https://adb-1234567890.12.azuredatabricks.net"


class DatabricksModelTests(unittest.TestCase):
    def test_settings_name_the_workspace_and_the_model(self):
        settings = load_settings({"CASEPATH_MODEL_PROVIDER": "databricks", "DATABRICKS_HOST": HOST[8:], "CASEPATH_MODEL": "claude-opus-5-5",
                                  "CASEPATH_MODEL_MAX_OUTPUT_TOKENS": "4000"})
        self.assertEqual((settings.model.provider, settings.model.endpoint, settings.model.deployment, settings.model.reasoning),
                         ("databricks", HOST, "claude-opus-5-5", False))
        with self.assertRaises(SettingsError):  # an arbitrary host stays refused
            load_settings({"CASEPATH_MODEL_PROVIDER": "databricks", "CASEPATH_MODEL_ENDPOINT": "https://api.example.com", "CASEPATH_MODEL": "m"})

    def test_the_agent_dialect_is_translated_both_ways(self):
        seen = []

        def handler(request):
            if request.url.path == "/oidc/v1/token":
                seen.append(("token", request.headers["authorization"].startswith("Basic ")))
                return httpx.Response(200, json={"access_token": "t-123", "expires_in": 3600})
            body = json.loads(request.content)
            seen.append(("chat", request.headers["authorization"], body))
            if "response_format" in body:
                return httpx.Response(200, json={"id": "c2", "choices": [{"finish_reason": "stop", "message": {"content": '{"ok": true}'}}],
                                                 "usage": {"prompt_tokens": 50, "completion_tokens": 5}})
            return httpx.Response(200, json={"id": "c1", "choices": [{"finish_reason": "tool_calls", "message": {"content": None, "tool_calls": [
                {"id": "call_1", "type": "function", "function": {"name": "record_fact", "arguments": '{"fact": "frist"}'}}]}}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 20, "prompt_tokens_details": {"cached_tokens": 60}}})

        transport = httpx.MockTransport(handler)
        env = {"CASEPATH_MODEL_PROVIDER": "databricks", "DATABRICKS_HOST": HOST, "CASEPATH_MODEL": "claude-opus-5-5"}
        settings = load_settings(env).model
        token = databricks_token_provider(HOST, {"DATABRICKS_CLIENT_ID": "id", "DATABRICKS_CLIENT_SECRET": "secret"}, transport=transport)
        model = ChatCompletionsModel(settings, token, transport=transport)
        tool = {"name": "record_fact", "description": "Record a fact.", "parameters": {"type": "object", "properties": {"fact": {"type": "string"}},
                                                                                          "required": ["fact"], "additionalProperties": False}}
        turn = model.respond(instructions="You are the claim reader.", input=[{"role": "user", "content": [
            {"type": "input_text", "text": "Page 1"}, {"type": "input_image", "image_url": "data:image/png;base64,AAAA", "detail": "high"}]}],
            tools=[tool], tool_choice={"type": "function", "name": "record_fact"})
        self.assertEqual(turn.calls, [{"call_id": "call_1", "name": "record_fact", "arguments": {"fact": "frist"}}])
        self.assertEqual(turn.usage, {"input_tokens": 100, "output_tokens": 20, "cached_tokens": 60})
        _, auth, body = seen[1]
        self.assertEqual((auth, body["model"], body["tool_choice"]), ("Bearer t-123", "claude-opus-5-5", {"type": "function", "function": {"name": "record_fact"}}))
        self.assertEqual(body["messages"][1]["content"][1], {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAA"}})
        # the next turn carries the call and its result as chat messages
        follow = to_messages("x", [{"role": "user", "content": "go"}, *turn.output,
                                   {"type": "function_call_output", "call_id": "call_1", "output": '{"accepted": true}'}])
        self.assertEqual([m["role"] for m in follow], ["system", "user", "assistant", "tool"])
        self.assertEqual(follow[2]["tool_calls"][0]["function"], {"name": "record_fact", "arguments": '{"fact": "frist"}'})
        result = model.respond_json(name="check", instructions="Check.", input=[{"role": "user", "content": "{}"}],
                                    schema={"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"], "additionalProperties": False})
        self.assertEqual(result.value, {"ok": True})
        self.assertEqual(sum(1 for s in seen if s[0] == "token"), 1)  # one sign-in, reused


if __name__ == "__main__":
    unittest.main()
