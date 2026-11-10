"""A scripted stand-in for the model: fixed turns, one per Responses API call.

The team calls the model strictly in sequence, agent after agent, so one ordered
list scripts a whole run. Lead turns (delegate, complete) in older scripts are
skipped: the lead is now a fixed plan that does not call the model.
"""
import json
import types

from casepath.agents.azure_model import ModelResult, Turn


class ScriptedModel:
    def __init__(self, turns, verdicts=None, default_verdict="supported", second_reading=None, routing=(), first_reading=None):
        self.turns = [t for t in turns if not t or not all(name in {"delegate", "complete"} for name, _ in t)]
        self.verdicts, self.default = verdicts or {}, default_verdict
        # The readings of the facts. By default the first reading is the claim reader's scripted record_fact calls (the
        # turns up to its report), and the second reading agrees with it.
        self.first_reading = None if first_reading is None else list(first_reading)
        self.second_reading = None if second_reading is None else list(second_reading)
        self.last_first_reading = []
        self.routing = list(routing)
        self.other_topic = []
        self.retries = {}  # name -> the answer to a retry
        self.confirm_documents = None  # the second judgment of documents, when a test sets it
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
        if len(input) > 1 and name in self.retries:  # a retry asks again in the same conversation
            value = self.retries[name]
            return ModelResult(value=value, usage={"input_tokens": 5}, deployment="d", response_id="q", attempts=1, seconds=0)
        if name == "casepath_confirm_documents":
            # By default the second judgment agrees with the finder: present, quoting the first file for every item.
            given = json.loads(input[0]["content"])
            first = given["files"][0]
            rows = self.confirm_documents if self.confirm_documents is not None else [
                {"document": n["document"], "status": "present", "file": first["file"],
                 "shows": [{"item": i, "quote": first["text"][:30]} for i in (n["must_show"] or ["the document"])]} for n in given["needs"]]
            return ModelResult(value={"documents": rows}, usage={"input_tokens": 5}, deployment="d", response_id="cd", attempts=1, seconds=0)
        if name == "casepath_route":
            from casepath.agents.schema import validate_result
            value = {"facts": self.routing, "other_topic": self.other_topic}
            validate_result(value, schema)  # a routing answer is checked against its schema, as the connectors do
            return ModelResult(value=value, usage={"input_tokens": 5}, deployment="d", response_id="r",
                               attempts=1, seconds=0)
        if name == "casepath_read_facts":
            rows = self.first_reading if self.first_reading is not None else self._scripted_reading()
            self.last_first_reading = rows
            return ModelResult(value={"conditions": [_condition(r) for r in rows]}, usage={"input_tokens": 5}, deployment="d",
                               response_id="f", attempts=1, seconds=0)
        if name == "casepath_confirm_facts":
            parts = instructions.split("Conditions:\n", 1)
            asked = set(json.loads(parts[1])) if len(parts) == 2 else {r["fact"] for r in self.last_first_reading}
            rows = self.second_reading if self.second_reading is not None else [r for r in self.last_first_reading if r["fact"] in asked]
            return ModelResult(value={"conditions": [_condition(r) for r in rows]}, usage={"input_tokens": 5}, deployment="d",
                               response_id="s", attempts=1, seconds=0)
        items = json.loads(input[0]["content"])["items"]
        value = {"items": [{"item": i["item"], "verdict": self.verdicts.get(i["item"], self.default), "reason": "checked"} for i in items]}
        return ModelResult(value=value, usage={"input_tokens": 5}, deployment="d", response_id="v", attempts=1, seconds=0)


    def _scripted_reading(self):
        """The claim reader's scripted fact turns (up to and including its report) as one structured reading."""
        rows = []
        while self.turns:
            turn = self.turns.pop(0)
            for name, args in turn:
                args = args() if callable(args) else args
                if name == "record_fact":
                    rows.append({"fact": args["fact"], "status": "established" if args["status"] == "established" else "unknown",
                                 "value": args.get("value"), "citations": args.get("citations", [])})
            if any(name == "report" for name, _ in turn):
                break
        return rows


def _condition(row):
    """A scripted fact row ({fact, status, value, citations}) as the reading's answer for one condition."""
    quote = (row.get("citations") or [{}])[0].get("quote", "")
    if row["status"] != "established":
        return {"id": row["fact"], "verdict": "unresolved", "value": None, "quote": quote}
    folded = str(row["value"]).strip().lower()
    if folded in {"true", "yes", "ja"}:
        return {"id": row["fact"], "verdict": "true", "value": None, "quote": quote}
    if folded in {"false", "no", "nein"}:
        return {"id": row["fact"], "verdict": "false", "value": None, "quote": quote}
    return {"id": row["fact"], "verdict": "true", "value": row["value"], "quote": quote}


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
