"""A whole team run through the Messages connector, against a gateway as strict as the workspace's."""
import json
import unittest

import httpx

from casepath.agents.team import CaseTeam
from casepath.agents.anthropic_model import AnthropicMessagesModel
from casepath.config import load_settings
from tests.scripted import ScriptedModel
from tests.test_team import CASE, FILES, FIXTURE, standard_script


class StrictGateway:
    """Refuses temperature and forced tool choice, and enforces the Messages rules: alternating roles starting with the
    user, no empty text, every tool_use answered by a tool_result first thing in the next message, tools defined
    whenever tool blocks appear. Behind it, a scripted model plays the agents."""

    def __init__(self, scripted):
        self.scripted, self.bodies = scripted, []

    def check(self, body):
        assert "temperature" not in body, "temperature is rejected"
        assert body.get("tool_choice", {"type": "auto"})["type"] == "auto", "forced tool choice is rejected"
        messages = body["messages"]
        assert messages and messages[0]["role"] == "user"
        for a, b in zip(messages, messages[1:]):
            assert a["role"] != b["role"], "roles must alternate"
        for index, message in enumerate(messages):
            assert message["content"], "no empty message"
            assert all(block.get("text") for block in message["content"] if block["type"] == "text"), "no empty text"
            uses = [b["id"] for b in message["content"] if b["type"] == "tool_use"] if message["role"] == "assistant" else []
            if uses:
                reply = messages[index + 1]["content"]
                results = [b["tool_use_id"] for b in reply if b["type"] == "tool_result"]
                assert sorted(results) == sorted(uses), "each tool_use needs its tool_result"
                assert [b["type"] for b in reply[:len(results)]] == ["tool_result"] * len(results), "tool results come first"
        if any(b["type"] in {"tool_use", "tool_result"} for m in messages for b in m["content"]):
            assert body.get("tools"), "tool blocks need tools"

    def handler(self, request):
        body = json.loads(request.content)
        self.check(body)
        self.bodies.append(body)
        tools = body.get("tools") or []
        if len(tools) == 1 and tools[0]["name"].startswith("casepath_"):  # a structured answer
            text = "".join(b.get("text", "") for b in body["messages"][0]["content"] if b["type"] == "text")
            value = self.scripted.respond_json(name=tools[0]["name"], instructions="", input=[{"role": "user", "content": text}],
                                               schema=tools[0]["input_schema"]).value
            content = [{"type": "tool_use", "id": f"toolu_{len(self.bodies)}", "name": tools[0]["name"], "input": value}]
        else:  # an agent's turn
            turn = self.scripted.respond(instructions=body["system"][0]["text"], input=[],
                                         tools=[{"name": t["name"], "description": t["description"], "parameters": t["input_schema"]} for t in tools])
            content = [{"type": "tool_use", "id": f"toolu_{len(self.bodies)}_{i}", "name": c["name"], "input": c["arguments"]}
                       for i, c in enumerate(turn.calls)]
        return httpx.Response(200, json={"id": f"msg_{len(self.bodies)}", "stop_reason": "tool_use", "content": content,
                                         "usage": {"input_tokens": 100, "cache_read_input_tokens": 400, "output_tokens": 20}})


class MessagesTeamTests(unittest.TestCase):
    def test_a_whole_case_runs_through_the_messages_connector_without_forced_tools(self):
        script = standard_script(
            finder_calls=[("record_document", {"document": "customer_message", "status": "present", "files": ["f1"],
                                               "citations": [{"file": "f1", "quote": "Subject: Schimmel im Bad"}], "note": ""}),
                          ("record_document", {"document": "notice_letter", "status": "absent", "files": [], "citations": [], "note": ""})],
            result_fields={"reply": {"needed": True, "subject": "Re: Schimmel", "clauses": [
                {"text": "You told your landlord in writing.", "kind": "statement", "basis": ["fact:landlord_notified"]}]}})
        gateway = StrictGateway(ScriptedModel(script))
        settings = load_settings({"CASEPATH_MODEL_PROVIDER": "databricks", "DATABRICKS_HOST": "adb-1.1.azuredatabricks.net",
                                  "CASEPATH_MODEL": "m", "CASEPATH_MODEL_API": "messages", "CASEPATH_MODEL_FORCED_TOOLS": "false"}).model
        model = AnthropicMessagesModel(settings, lambda: "t", transport=httpx.MockTransport(gateway.handler))
        result = CaseTeam(model).run(case=CASE, files=FILES, workflow=FIXTURE)
        self.assertEqual(result["evaluation"]["outcome"]["id"], "reported")
        fact, = result["facts"]
        self.assertEqual((fact["value"], fact["verdict"]), (True, "accepted"))
        self.assertTrue(result["reply"]["clauses"][0]["supported"])
        self.assertGreater(len(gateway.bodies), 8)
        self.assertTrue(all(u.get("cached_tokens") == 400 for u in result["usage"]))  # the cached prefix is counted
        self.assertTrue(any("Act only through your tools" in b["system"][0]["text"] for b in gateway.bodies))


if __name__ == "__main__":
    unittest.main()
