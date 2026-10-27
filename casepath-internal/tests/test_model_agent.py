import json
from pathlib import Path
import unittest

import httpx

from casepath_internal.agent import AgentError, CaseAgent
from casepath_internal.azure_model import AzureOpenAIModel, ModelError, ModelResult, Turn
from casepath_internal.config import ModelSettings, SettingsError, load_settings
from casepath_internal.schema import obj, text

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "example-defect.json").read_text())
ENDPOINT = "https://example-resource.openai.azure.com"


def settings(reasoning=True):
    return ModelSettings(endpoint=ENDPOINT, deployment="example-deployment", reasoning=reasoning, timeout_seconds=5,
                         max_output_tokens=1000, ca_bundle=None, trust_env=False)


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


FILES = [
    {"id": "f1", "name": "message.eml", "kind": "email", "text": "Subject: Schimmel im Bad\n\nIch habe den Vermieter am 2. März schriftlich informiert."},
    {"id": "f2", "name": "photo.jpg", "kind": "image", "text": "", "note": "Kept as an original."},
]
FINISH = {"summary": "The tenant reports mould and told the landlord.", "answer": "The landlord was told; evidence is incomplete.",
          "open_points": ["No photo text"], "reply": {"needed": True, "subject": "Re: Schimmel im Bad", "clauses": [
              {"text": "You told your landlord in writing.", "basis": ["fact:landlord_notified"]},
              {"text": "We still need the notice letter.", "basis": ["document:notice_letter"]}]},
          "lessons": [{"text": "Ask for the written notice.", "applies_when": "defect cases", "citations": [
              {"file": "f1", "quote": "Ich habe den Vermieter am 2. März schriftlich informiert."}]}]}


class AgentTests(unittest.TestCase):
    def run_agent(self, turns, verdict="supported"):
        model = ScriptedModel(turns, verdict)
        return CaseAgent(model).run(case={"title": "Example"}, files=FILES, workflow=FIXTURE), model

    def test_case_prepared_with_located_and_verified_findings(self):
        quote = "Ich habe den Vermieter am 2. März schriftlich informiert."
        result, model = self.run_agent([
            [("open_workflow", {}), ("list_files", {})],
            [("record_fact", {"fact": "landlord_notified", "status": "established", "value": "yes",
                              "citations": [{"file": "f1", "quote": quote}]}),
             ("record_fact", {"fact": "legal_area", "status": "established", "value": "tenancy_defect",
                              "citations": [{"file": "f1", "quote": "Schimmel im Bad, frei erfunden"}]}),
             ("record_document", {"document": "customer_message", "status": "present", "files": ["f1"],
                                  "citations": [{"file": "f1", "quote": "Subject: Schimmel im Bad"}], "note": ""}),
             ("record_document", {"document": "notice_letter", "status": "absent", "files": [], "citations": [], "note": ""})],
            [("evaluate", {}), ("finish", FINISH)],
        ])
        self.assertIn("record_fact", model.seen[0])
        facts = {f["fact"]: f for f in result["facts"]}
        self.assertEqual(facts["landlord_notified"]["value"], True)
        self.assertEqual(facts["landlord_notified"]["verdict"], "accepted")
        self.assertNotIn("legal_area", facts)  # its quote is not in the file
        evaluation = result["evaluation"]
        self.assertEqual(evaluation["outcome"]["id"], "reported")
        statuses = {d["document"]: d["status"] for d in evaluation["documents"]}
        self.assertEqual(statuses, {"customer_message": "present", "photo": "missing", "notice_letter": "missing"})
        self.assertEqual([c["supported"] for c in result["reply"]["clauses"]], [True, True])
        self.assertEqual(result["reply"]["status"], "draft_not_sent")
        self.assertEqual(len(result["lessons"]), 1)
        roles = {e["role"] for e in result["events"]}
        self.assertTrue({"claim_reader", "process_builder", "document_finder", "source_checker", "result_checker"} <= roles)

    def test_independent_check_can_overrule(self):
        quote = "Ich habe den Vermieter am 2. März schriftlich informiert."
        result, _ = self.run_agent([
            [("record_fact", {"fact": "landlord_notified", "status": "established", "value": "yes",
                              "citations": [{"file": "f1", "quote": quote}]})],
            [("finish", FINISH)],
        ], verdict="uncertain")
        self.assertEqual(result["facts"][0]["verdict"], "rejected")
        self.assertEqual(result["evaluation"]["current"]["step"], "notice")
        self.assertEqual(result["reply"]["clauses"][0]["supported"], False)

    def test_bad_arguments_are_returned_to_the_model(self):
        result, _ = self.run_agent([
            [("record_fact", {"fact": "landlord_notified", "status": "established", "value": "maybe",
                              "citations": [{"file": "f1", "quote": "Ich habe den Vermieter am 2. März schriftlich informiert."}]}),
             ("read_file", {"file": "nope", "from_page": None, "to_page": None})],
            [("finish", FINISH)],
        ])
        self.assertEqual(result["facts"], [])
        self.assertIn("fact.rejected", [e["kind"] for e in result["events"]])

    def test_turn_limit(self):
        model = ScriptedModel([[("list_files", {})]] * 3)
        with self.assertRaises(AgentError) as caught:
            CaseAgent(model, max_turns=3).run(case={}, files=FILES, workflow=FIXTURE)
        self.assertEqual(caught.exception.reason, "turn_limit")


if __name__ == "__main__":
    unittest.main()
