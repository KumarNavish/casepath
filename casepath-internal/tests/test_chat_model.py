import json
import unittest

import httpx

from casepath_internal.chat_model import ChatCompletionsModel, databricks_token_provider, to_messages
from casepath_internal.config import SettingsError, load_settings

HOST = "https://adb-1234567890.12.azuredatabricks.net"


class DatabricksModelTests(unittest.TestCase):
    def test_settings_name_the_workspace_and_the_model(self):
        settings = load_settings({"CASEPATH_MODEL_PROVIDER": "databricks", "DATABRICKS_HOST": HOST[8:], "CASEPATH_MODEL": "gateway-model-1",
                                  "CASEPATH_MODEL_MAX_OUTPUT_TOKENS": "4000"})
        self.assertEqual((settings.model.provider, settings.model.endpoint, settings.model.deployment, settings.model.reasoning),
                         ("databricks", HOST, "gateway-model-1", False))
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
        env = {"CASEPATH_MODEL_PROVIDER": "databricks", "DATABRICKS_HOST": HOST, "CASEPATH_MODEL": "gateway-model-1"}
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
        self.assertEqual((auth, body["model"], body["tool_choice"]), ("Bearer t-123", "gateway-model-1", {"type": "function", "function": {"name": "record_fact"}}))
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


class UserTokenTests(unittest.TestCase):
    def test_the_model_can_be_called_as_the_person_who_starts_the_run(self):
        import tempfile
        from fastapi.testclient import TestClient
        from casepath_internal.app import create_app, default_model_factory
        with tempfile.TemporaryDirectory() as data:
            env = {"CASEPATH_DATA_DIR": data, "CASEPATH_IDENTITY_HEADER": "X-Forwarded-Email", "CASEPATH_MODEL_PROVIDER": "databricks",
                   "DATABRICKS_HOST": HOST, "CASEPATH_MODEL": "m", "CASEPATH_MODEL_AUTH": "user"}
            settings = load_settings(env)
            factory = default_model_factory(settings)
            self.assertIsNone(factory())  # no person, no model
            model = factory("person-token")
            self.assertEqual(model._token(), "person-token")
            client = TestClient(create_app(settings, model_factory=lambda token=None: None))
            who = {"X-Forwarded-Email": "anna@example.ch"}
            case = client.post("/api/cases", json={"title": "x"}, headers=who).json()
            self.assertEqual(client.post(f"/api/cases/{case['id']}/runs", headers=who).status_code, 401)
            self.assertEqual(client.post(f"/api/cases/{case['id']}/runs", headers={**who, "X-Forwarded-Access-Token": "t"}).status_code, 202)
            client.app.state.runs.shutdown()
            client.app.state.store.close()
        with self.assertRaises(SettingsError):
            load_settings({"CASEPATH_AZURE_OPENAI_ENDPOINT": "https://r.openai.azure.com", "CASEPATH_AZURE_OPENAI_DEPLOYMENT": "d", "CASEPATH_MODEL_AUTH": "user"})


class StructuredAnswerFallbackTests(unittest.TestCase):
    def test_an_endpoint_without_response_format_answers_through_a_forced_tool(self):
        bodies = []

        def handler(request):
            body = json.loads(request.content)
            bodies.append(body)
            if "response_format" in body:
                return httpx.Response(400, json={"error": {"code": "invalid_parameter_value"}})
            return httpx.Response(200, json={"id": "c", "choices": [{"finish_reason": "tool_calls", "message": {"content": None, "tool_calls": [
                {"id": "t1", "type": "function", "function": {"name": "check", "arguments": '{"ok": true}'}}]}}], "usage": {}})
        transport = httpx.MockTransport(handler)
        settings = load_settings({"CASEPATH_MODEL_PROVIDER": "databricks", "DATABRICKS_HOST": HOST, "CASEPATH_MODEL": "m",
                                  "CASEPATH_CHAT_PATH": "/ai-gateway/mlflow/v1/chat/completions"}).model
        model = ChatCompletionsModel(settings, lambda: "t", transport=transport)
        self.assertEqual(model.url, HOST + "/ai-gateway/mlflow/v1/chat/completions")
        schema = {"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"], "additionalProperties": False}
        for _ in range(2):
            self.assertEqual(model.respond_json(name="check", instructions="x", input=[{"role": "user", "content": "{}"}], schema=schema).value, {"ok": True})
        self.assertEqual([("response_format" in b, b.get("tool_choice")) for b in bodies],
                         [(True, None), (False, {"type": "function", "function": {"name": "check"}}),
                          (False, {"type": "function", "function": {"name": "check"}})])  # tried once, then remembered



class MessagesApiTests(unittest.TestCase):
    def test_the_agent_dialect_runs_on_the_messages_api_with_caching(self):
        from casepath_internal.anthropic_model import AnthropicMessagesModel, to_messages as to_blocks
        bodies = []

        def handler(request):
            body = json.loads(request.content)
            bodies.append(body)
            if any("cache_control" in json.dumps(m) for m in body["messages"]) and len(bodies) == 1:
                return httpx.Response(400, json={"error_code": "BAD_REQUEST"})  # a gateway that refuses cache marks
            name = body["tools"][0]["name"]
            return httpx.Response(200, json={"id": "m1", "stop_reason": "tool_use", "content": [
                {"type": "text", "text": "Recording."}, {"type": "tool_use", "id": "tu_1", "name": name, "input": {"ok": True} if name == "check" else {"fact": "frist"}}],
                "usage": {"input_tokens": 40, "cache_read_input_tokens": 60, "output_tokens": 9}})
        settings = load_settings({"CASEPATH_MODEL_PROVIDER": "databricks", "DATABRICKS_HOST": HOST, "CASEPATH_MODEL": "m", "CASEPATH_MODEL_API": "messages"}).model
        model = AnthropicMessagesModel(settings, lambda: "t", transport=httpx.MockTransport(handler))
        self.assertEqual(model.url, HOST + "/ai-gateway/anthropic/v1/messages")
        tool = {"name": "record_fact", "description": "Record.", "parameters": {"type": "object", "properties": {"fact": {"type": "string", "maxLength": 80}},
                                                                                 "required": ["fact"], "additionalProperties": False}}
        turn = model.respond(instructions="You are the claim reader.", input=[{"role": "user", "content": [
            {"type": "input_text", "text": "Page 1"}, {"type": "input_image", "image_url": "data:image/png;base64,AAAA"}]}], tools=[tool], tool_choice="required")
        self.assertEqual(turn.calls, [{"call_id": "tu_1", "name": "record_fact", "arguments": {"fact": "frist"}}])
        self.assertEqual(turn.usage, {"input_tokens": 100, "output_tokens": 9, "cached_tokens": 60})
        first, second = bodies
        self.assertEqual(second["tool_choice"], {"type": "any"})
        self.assertNotIn("cache_control", json.dumps(second))  # retried without the marks, and remembered
        self.assertEqual(first["system"][0]["cache_control"], {"type": "ephemeral"})
        self.assertEqual(second["messages"][0]["content"][1], {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "AAAA"}})
        self.assertNotIn("maxLength", json.dumps(second["tools"]))  # bounds are checked locally, not sent
        # a carried turn becomes tool_use, its results one user message with tool_result and the nudge
        follow = to_blocks([{"role": "user", "content": "go"}, *turn.output,
                            {"type": "function_call_output", "call_id": "tu_1", "output": '{"accepted": true}'},
                            {"role": "user", "content": "Continue with your tools, then call report."}])
        self.assertEqual([m["role"] for m in follow], ["user", "assistant", "user"])
        self.assertEqual([b["type"] for b in follow[1]["content"]], ["text", "tool_use"])
        self.assertEqual([b["type"] for b in follow[2]["content"]], ["tool_result", "text"])
        result = model.respond_json(name="check", instructions="Check.", input=[{"role": "user", "content": "{}"}],
                                    schema={"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"], "additionalProperties": False})
        self.assertEqual(result.value, {"ok": True})
        self.assertEqual(bodies[-1]["tool_choice"], {"type": "tool", "name": "check"})

if __name__ == "__main__":
    unittest.main()
