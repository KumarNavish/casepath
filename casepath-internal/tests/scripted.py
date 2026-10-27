"""A scripted stand-in for the model: fixed turns, one per Responses API call.

The team calls the model strictly in sequence (the lead, then the agent it
delegates to, then the lead again), so one ordered list scripts a whole run.
"""
import json
import types

from casepath_internal.azure_model import ModelResult, Turn


class ScriptedModel:
    def __init__(self, turns, verdicts=None, default_verdict="supported"):
        self.turns, self.verdicts, self.default = list(turns), verdicts or {}, default_verdict
        self.instructions, self.tools = [], []
        self.settings = types.SimpleNamespace(deployment="example-deployment")

    def respond(self, *, instructions, input, tools=(), text_schema=None, effort="medium"):
        if not self.turns:
            raise AssertionError("the script has no turn left")
        self.instructions.append(instructions.split("\n\n")[-1][:40])
        self.tools.append([t["name"] for t in tools])
        calls = [{"call_id": f"c{len(self.tools)}-{i}", "name": name, "arguments": args() if callable(args) else args}
                 for i, (name, args) in enumerate(self.turns.pop(0))]
        return Turn(output=[{"type": "function_call", **c, "arguments": json.dumps(c["arguments"])} for c in calls],
                    calls=calls, text="", usage={"input_tokens": 10, "output_tokens": 2}, response_id="r",
                    status="completed", attempts=1, seconds=0)

    def respond_json(self, *, name, instructions, input, schema, effort="medium"):
        items = json.loads(input[0]["content"])["items"]
        value = {"items": [{"item": i["item"], "verdict": self.verdicts.get(i["item"], self.default), "reason": "checked"} for i in items]}
        return ModelResult(value=value, usage={"input_tokens": 5}, deployment="d", response_id="v", attempts=1, seconds=0)


def delegate(agent, instruction="Do your part."):
    return ("delegate", {"agent": agent, "instruction": instruction})


def report(agent, **fields):
    defaults = {
        "claim_reader": {"summary": "Read.", "request": "", "parties": [], "timeline": []},
        "process_builder": {"summary": "Built.", "questions": []},
        "document_finder": {"summary": "Found."},
        "result_checker": {"summary": "Checked.", "answer": "An answer.", "open_points": [],
                           "reply": {"needed": False, "subject": "", "clauses": []}, "learn": [], "case_summary": []},
    }
    return ("report", {**defaults[agent], **fields})


def learn(**fields):
    row = {"action": "new", "target": None, "kind": "document_need", "title": "", "why": "", "question": "", "note": "",
           "step": None, "applies_when": [], "applies_when_text": "", "reason": "Seen in this case.", "citations": []}
    return {**row, **fields}
