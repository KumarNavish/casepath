"""A scripted stand-in for the model: fixed turns, one per Responses API call.

The team calls the model strictly in sequence, agent after agent, so one ordered
list scripts a whole run. Lead turns (delegate, complete) in older scripts are
skipped: the lead is now a fixed plan that does not call the model.
"""
import json
import types

from casepath.agents.azure_model import ModelResult, Turn


class ScriptedModel:
    def __init__(self, turns, verdicts=None, default_verdict="supported", second_reading=(), routing=()):
        self.turns = [t for t in turns if not t or not all(name in {"delegate", "complete"} for name, _ in t)]
        self.verdicts, self.default, self.second_reading = verdicts or {}, default_verdict, list(second_reading)
        self.routing = list(routing)
        self.tool_choices = []
        self.instructions, self.tools, self.inputs = [], [], []
        self.settings = types.SimpleNamespace(deployment="example-deployment")

    def respond(self, *, instructions, input, tools=(), text_schema=None, effort="medium", tool_choice=None):
        self.tool_choices.append(tool_choice)
        self.inputs.append(input)  # a scripted argument can be a function that reads what the agent was given
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
        if name == "casepath_photo":
            return ModelResult(value={"description": "[Foto] Wand mit dunklen Flecken neben dem Fenster."}, usage={"input_tokens": 5},
                               deployment="d", response_id="p", attempts=1, seconds=0)
        if name == "casepath_route":
            return ModelResult(value={"facts": self.routing}, usage={"input_tokens": 5}, deployment="d", response_id="r",
                               attempts=1, seconds=0)
        if name == "casepath_confirm_facts":
            return ModelResult(value={"facts": self.second_reading}, usage={"input_tokens": 5}, deployment="d", response_id="s",
                               attempts=1, seconds=0)
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
