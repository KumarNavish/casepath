import json
from pathlib import Path
import unittest

import httpx

from casepath_internal.azure_model import AzureOpenAIModel, ModelError, ModelResult, Turn, in_cloud_shell, token_provider
from casepath_internal.config import ModelSettings, SettingsError, load_settings
from casepath_internal.schema import obj, text

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "example-defect.json").read_text())
ENDPOINT = "https://example-resource.openai.azure.com"


def settings(reasoning=True, api_version=None):
    return ModelSettings(endpoint=ENDPOINT, deployment="example-deployment", reasoning=reasoning, timeout_seconds=5,
                         max_output_tokens=1000, ca_bundle=None, trust_env=False, api_version=api_version)


class SettingsTests(unittest.TestCase):
    def test_only_azure_resource_endpoints(self):
        for endpoint in ("https://openrouter.ai", "https://api.openai.com", "http://example-resource.openai.azure.com",
                         ENDPOINT + "/openai/v1"):
            with self.assertRaises(SettingsError):
                ModelSettings(endpoint=endpoint, deployment="d", reasoning=True, timeout_seconds=5, max_output_tokens=1,
                              ca_bundle=None, trust_env=False)

    def test_environment(self):
        loaded = load_settings({"CASEPATH_AZURE_OPENAI_ENDPOINT": ENDPOINT + "/", "CASEPATH_AZURE_OPENAI_DEPLOYMENT": "x-gpt-5.6-sol-model",
                                "CASEPATH_DEV_USER": "dev"})
        self.assertTrue(loaded.model.reasoning)
        self.assertEqual(loaded.model.endpoint, ENDPOINT)
        with self.assertRaises(SettingsError):
            load_settings({"CASEPATH_IDENTITY_HEADER": "x-identity", "CASEPATH_DEV_USER": "dev"})


class Credential:
    def __init__(self, outcome, delay=0):
        self.outcome, self.delay, self.calls = outcome, delay, 0

    def get_token(self, scope):
        import time
        from types import SimpleNamespace
        self.calls += 1
        time.sleep(self.delay)
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return SimpleNamespace(token=self.outcome, expires_on=time.time() + 3600)


class SignInTests(unittest.TestCase):
    def test_a_slow_or_failing_source_is_named_and_the_next_one_is_tried(self):
        cli, managed = Credential(RuntimeError("Timeout waiting for token from portal\nmore"), 0), Credential("tok")
        provider = token_provider([("az", cli), ("managed identity", managed)], "scope", timeout=1)
        self.assertEqual(provider(), "tok")
        self.assertEqual(provider(), "tok")
        self.assertEqual(managed.calls, 1)  # cached until shortly before expiry

    def test_a_hanging_source_times_out_with_its_reason(self):
        provider = token_provider([("az", Credential("late", delay=2))], "scope", timeout=0.2, hint=" Try az login.")
        with self.assertRaises(ModelError) as caught:
            provider()
        self.assertEqual(caught.exception.reason, "sign_in")
        self.assertIn("az: no answer within 0.2 s", str(caught.exception))
        self.assertIn("Try az login.", str(caught.exception))

    def test_cloud_shell_is_recognised(self):
        self.assertTrue(in_cloud_shell({"AZUREPS_HOST_ENVIRONMENT": "cloud-shell/1.0"}))
        self.assertFalse(in_cloud_shell({}))


class ModelTests(unittest.TestCase):
    def model(self, handler, **kw):
        return AzureOpenAIModel(settings(**kw), lambda: "token-value", transport=httpx.MockTransport(handler), sleep=lambda s: None)

    def test_responses_request_shape(self):
        seen = {}

        def handler(request):
            seen["url"], seen["auth"], seen["body"] = str(request.url), request.headers["authorization"], json.loads(request.content)
            return httpx.Response(200, json={"id": "r1", "status": "completed", "usage": {"input_tokens": 5, "output_tokens": 2},
                                             "output": [{"type": "reasoning", "encrypted_content": "e"},
                                                        {"type": "function_call", "call_id": "c1", "name": "list_files", "arguments": "{}"}]})

        tool = {"name": "list_files", "description": "d", "parameters": obj(q=text(10, minLength=1))}
        turn = self.model(handler).respond(instructions="i", input=[{"role": "user", "content": "x"}], tools=[tool])
        self.assertEqual(seen["url"], ENDPOINT + "/openai/v1/responses")
        self.assertEqual(seen["auth"], "Bearer token-value")
        body = seen["body"]
        self.assertIs(body["store"], False)
        self.assertEqual(body["include"], ["reasoning.encrypted_content"])
        self.assertTrue(body["tools"][0]["strict"])
        self.assertNotIn("maxLength", json.dumps(body["tools"]))
        self.assertNotIn("provider", body)
        self.assertEqual(turn.calls, [{"call_id": "c1", "name": "list_files", "arguments": {}}])
        self.assertEqual(len(turn.output), 2)

    def test_dated_api_routes_when_a_version_is_configured(self):
        urls = []

        def handler(request):
            urls.append(str(request.url))
            if "chat" in str(request.url):
                return httpx.Response(200, json={"id": "c", "choices": [{"finish_reason": "stop", "message": {"content": '{"q": "ok"}'}}]})
            return httpx.Response(200, json={"id": "r", "status": "completed", "output": []})

        model = self.model(handler, api_version="2025-04-01-preview")
        model.respond(instructions="i", input=[])
        model.complete_json(name="n", system="s", user="u", schema=obj(q=text(10)))
        self.assertEqual(urls, [ENDPOINT + "/openai/responses?api-version=2025-04-01-preview",
                                ENDPOINT + "/openai/deployments/example-deployment/chat/completions?api-version=2025-04-01-preview"])

    def test_retries_then_reports_status(self):
        calls = []

        def handler(request):
            calls.append(1)
            return httpx.Response(429 if len(calls) == 1 else 400, json={"error": {"code": "bad_request"}})

        with self.assertRaises(ModelError) as caught:
            self.model(handler).respond(instructions="i", input=[])
        self.assertEqual((caught.exception.reason, caught.exception.attempts), ("http_400", 2))

    def test_structured_answer_is_validated_locally(self):
        def handler(request):
            return httpx.Response(200, json={"id": "r", "status": "completed",
                                             "output": [{"type": "message", "content": [{"type": "output_text", "text": '{"a": "too long"}'}]}]})

        with self.assertRaises(ModelError) as caught:
            self.model(handler).respond_json(name="n", instructions="i", input=[], schema=obj(a=text(3)))
        self.assertEqual(caught.exception.reason, "schema_mismatch")

    def test_chat_completions_for_non_reasoning_deployments(self):
        def handler(request):
            body = json.loads(request.content)
            self.assertEqual(body["temperature"], 0)
            self.assertTrue(request.url.path.endswith("/openai/v1/chat/completions"))
            return httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {"content": '{"a": "ok"}'}}]})

        result = self.model(handler, reasoning=False).complete_json(name="n", system="s", user="u", schema=obj(a=text(3)))
        self.assertEqual(result.value, {"a": "ok"})


class ScriptedModel:
    """Plays fixed tool calls turn by turn, then answers the verification pass."""
    def __init__(self, turns, verdict="supported"):
        self.turns, self.verdict, self.seen = list(turns), verdict, []

    def respond(self, *, instructions, input, tools=(), text_schema=None, effort="medium"):
        self.seen.append([t["name"] for t in tools])
        calls = [{"call_id": f"c{i}", "name": name, "arguments": args} for i, (name, args) in enumerate(self.turns.pop(0))]
        return Turn(output=[{"type": "function_call", **c, "arguments": json.dumps(c["arguments"])} for c in calls],
                    calls=calls, text="", usage={}, response_id="r", status="completed", attempts=1, seconds=0)

    def respond_json(self, *, name, instructions, input, schema, effort="medium"):
        items = json.loads(input[0]["content"])["items"]
        return ModelResult(value={"items": [{"item": i["item"], "verdict": self.verdict, "reason": "checked"} for i in items]},
                           usage={}, deployment="d", response_id="v", attempts=1, seconds=0)


