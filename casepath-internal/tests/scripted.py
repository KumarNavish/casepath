"""A scripted stand-in for the model: fixed turns, one per Responses API call.

The team calls the model strictly in sequence, agent after agent, so one ordered
list scripts a whole run. Lead turns (delegate, complete) in older scripts are
skipped: the lead is now a fixed plan that does not call the model.
"""
import json
import types

from casepath.agents.azure_model import ModelResult, Turn


class ScriptedModel:
    sequential = True  # its turns are one ordered script

    def __init__(self, turns, verdicts=None, default_verdict="supported", second_reading=(), routing=(), other_topic=()):
        self.turns = [t for t in turns if not t or not all(name in {"delegate", "complete"} for name, _ in t)]
        self.verdicts, self.default, self.second_reading = verdicts or {}, default_verdict, list(second_reading)
        self.routing, self.other_topic = list(routing), list(other_topic)  # the routing facts the reader "finds", with quotes
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
            return ModelResult(value={"facts": self.routing, "other_topic": self.other_topic}, usage={"input_tokens": 5}, deployment="d",
                               response_id="route", attempts=1, seconds=0)
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
        "claim_reader": {"summary": "Read.", "request": "", "parties": [], "timeline": [], "not_enclosed": [], "questions": [], "claims": []},
        "process_builder": {"summary": "Built.", "questions": []},
        "document_finder": {"summary": "Found."},
        "result_checker": {"summary": "Checked.", "answer": "An answer.", "open_points": [],
                           "reply": {"needed": False, "subject": "", "clauses": []}, "learn": [], "case_summary": []},
    }
    return ("report", {**defaults[agent], **fields})


def question(text, quote, about=(), file="f1"):
    """A customer's question as the reader lists it: its words, the sentence that asks it, and the key points whose rule
    it asks about (``about``, the reader's tags)."""
    return {"question": text, "citations": [{"file": file, "quote": quote}], "about": list(about)}


def period(first="", last=""):
    """A period as the reader records it: {from, to} as YYYY-MM-DD, empty where not written."""
    return {"from": first, "to": last}


def claim(what, quote, amount=None, file="f1", role="requested", expense="", kind="andere", party="", when=None, transaction=""):
    """A cost the customer asks to have compensated, as the reader lists it: a few words of the customer's sentence, the
    amount as written, its role, what it is about (``expense`` in words and its ``kind``, who billed it, the period
    ``when``, the number) and that sentence. Its receipt is recorded on the receipt's own entry (``receipt``)."""
    return {"what": what, "amount": amount or "", "role": role, "expense": expense or what, "expense_kind": kind, "party": party,
            "period": when or period(), "transaction": transaction, "citations": [{"file": file, "quote": quote}]}


def receipt(quote, expense, kind, amount="", role="paid", party="", payer="kunde", when=None, transaction=""):
    """What a receipt, bill or credit note records, as the reader gives it on the entry of its document: what it is for (in
    its words and its kind), who issued it, whom it bills, the period, the number, the amount as written and its role, and
    the words that state the amount."""
    return {"expense": expense, "expense_kind": kind, "party": party, "payer": payer, "period": when or period(), "transaction": transaction,
            "amount": amount, "role": role, "quote": quote}


def learn(**fields):
    row = {"action": "new", "target": None, "kind": "document_need", "title": "", "why": "", "question": "", "note": "",
           "step": None, "applies_when": [], "applies_when_text": "", "reason": "Seen in this case.", "citations": []}
    return {**row, **fields}
