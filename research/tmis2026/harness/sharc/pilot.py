"""ShARC decision-making pilot on a TRAIN-split sample: CP4's core versus prompting baselines, same small model.

Designs (gpt-6-luna, low reasoning effort, schema-constrained output, inputs: snippet, question, scenario, history):
  direct   one prompt, the four decisions defined, answer with the class
  steps    one prompt: list the rule's conditions, judge each, combine, decide (Chain-of-Logic style)
  sc3      'steps' three times (runs 0, 1, 2; run 0 is the 'steps' call), majority vote, ties -> Inquire
  cp       CasePath core: call A (snippet + question only -> conditions, formula, addresses_question; cached by
           (snippet, question)), calls B1/B2 (two independent readings with exact quotations), quotation admission
           as in v2/cp4.py, agreement, then code: exact deferral over the unresolved conditions.
  Model-free ablations from the same judgments: cp_kleene (strong Kleene instead of exact deferral),
  cp_single (reading B1 only instead of two agreeing readings).

Run with python3 -I. Usage:
  TMIS_MODEL=openai/gpt-6-luna TMIS_BUDGET_USD=2.50 python3 -I pilot.py <sharc_train.json> --ids dev60|all
      --designs cp,direct,steps,sc3 [--cp-version v1]
The dev split is never read: the data path must name sharc_train.json.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "v2"))
sys.path.insert(0, str(HERE.parent))
import common  # noqa: E402  (installs the transport-retrying llm.call)
import llm  # noqa: E402
import match  # noqa: E402  (V6 normalised quotation matcher, as in cp4.py)

assert llm.MODEL == "openai/gpt-6-luna", "pilot is gpt-6-luna only"
OUT = HERE.parents[1] / "runs" / "sharc"
OUT.mkdir(parents=True, exist_ok=True)
llm.LEDGER = OUT / "ledger_pilot_gpt-6-luna.jsonl"  # never the shared ledgers
CLASSES = ["Yes", "No", "Irrelevant", "Inquire"]


def label(answer):
    return answer if answer in ("Yes", "No", "Irrelevant") else "Inquire"


def h(*parts):
    return hashlib.sha256("\x1f".join(parts).encode()).hexdigest()[:16]


# ---------------------------------------------------------------- inputs

def history_lines(u):
    return [f"Q: {t['follow_up_question']} A: {t['follow_up_answer']}" for t in u["history"]]


def facts_text(u):
    """The only text a quotation may come from: the scenario and the rendered history lines."""
    return (u["scenario"] or "") + "\n" + "\n".join(history_lines(u))


def case_block(u):
    hist = "\n".join(history_lines(u)) or "(none)"
    return (f"RULE TEXT:\n{u['snippet']}\n\nQUESTION:\n{u['question']}\n\nSCENARIO:\n{u['scenario'] or '(none)'}"
            f"\n\nHISTORY (follow-up questions already asked, with the user's answers):\n{hist}")


# ---------------------------------------------------------------- baselines

DEFS = """You answer a user's question using only a rule text, in a conversation. You are given the rule text, the user's
question, the user's scenario (may be empty) and a history of follow-up questions already asked with the user's
yes/no answers. Decide exactly one of:
- Yes: the rule text answers the question and, with the user's facts from the scenario and history, the answer is yes.
- No: the rule text answers the question and, with the user's facts from the scenario and history, the answer is no.
- Irrelevant: the rule text does not address the question; it could not answer it whatever the user's facts.
- Inquire: the rule text addresses the question, but the answer depends on a fact about the user that the scenario
  and history do not establish, so a follow-up question must be asked first.
Use only facts the user has stated or that follow directly from them; do not assume facts that are not stated."""

DIRECT_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["decision"],
                 "properties": {"decision": {"type": "string", "enum": CLASSES}}}

STEPS_TASK = DEFS + """

Work step by step before deciding: (1) list the conditions the rule text sets for the answer to the question to be
yes; (2) judge each condition as met, not met or unknown from the scenario and history, with the basis; (3) state how
the conditions combine (and / or / not) and what that gives; (4) decide."""

STEPS_SCHEMA = {"type": "object", "additionalProperties": False,
                "required": ["rule_addresses_question", "conditions", "combination", "decision"],
                "properties": {
                    "rule_addresses_question": {"type": "boolean"},
                    "conditions": {"type": "array", "items": {
                        "type": "object", "additionalProperties": False, "required": ["condition", "status", "basis"],
                        "properties": {"condition": {"type": "string"},
                                       "status": {"type": "string", "enum": ["met", "not met", "unknown"]},
                                       "basis": {"type": "string"}}}},
                    "combination": {"type": "string"},
                    "decision": {"type": "string", "enum": CLASSES}}}


def run_direct(u, run=0):
    r = llm.call(system=DEFS + "\n\nAnswer with the decision only.", user=case_block(u), schema=DIRECT_SCHEMA,
                 schema_name="decision", run=run, tag={"exp": "sharc-pilot", "method": "direct", "case": u["utterance_id"]})
    return {"decision": (r["result"] or {}).get("decision"), "error": r["error"]}


def run_steps(u, run=0):
    r = llm.call(system=STEPS_TASK, user=case_block(u), schema=STEPS_SCHEMA, schema_name="stepwise_decision", run=run,
                 tag={"exp": "sharc-pilot", "method": "steps" if run == 0 else "sc3", "case": u["utterance_id"]})
    return {"decision": (r["result"] or {}).get("decision"), "error": r["error"], "trace": r["result"]}


def run_sc3(u):
    votes = [run_steps(u, run)["decision"] for run in range(3)]
    counts = {c: votes.count(c) for c in CLASSES}
    top = max(counts.values())
    winners = [c for c in CLASSES if counts[c] == top]
    return {"decision": winners[0] if len(winners) == 1 else "Inquire", "votes": votes}


# ---------------------------------------------------------------- CasePath core

CP_PROMPTS = {
    "v1": {
        "A": """You formalise a rule text for one yes/no question. You see only the rule text and the question, not the
user's situation.
1. addresses_question: true if the rule text, given suitable facts about the user, settles the answer to the question
   (yes or no); false if the rule text is about something else and could not answer the question whatever the facts.
2. conditions: the atomic yes/no statements about the user or the user's situation on which the rule text makes the
   answer depend, in the rule's own words as far as possible, ids c1, c2, ... Split lists of requirements and lists
   of alternatives into one condition per item.
3. formula: a Boolean formula over the condition ids with and, or, not and parentheses that is true exactly when the
   answer to the question is yes according to the rule text.
If addresses_question is false, give no conditions and the formula "false".""",
        "B": """You check conditions about a user against what the user has told us: a scenario and a history of follow-up
questions with the user's yes/no answers. For each condition give:
- true: the scenario or history establishes that it holds;
- false: the scenario or history establishes that it does not hold;
- unresolved: neither settles it.
With every true or false verdict give an exact quotation, copied character for character, of the words that settle it:
a sentence or phrase of the scenario, or a whole history line ("Q: ... A: ...") when a follow-up question asks the
condition (or its opposite) and the user's answer settles it. For unresolved give an empty quote. Use only what the
user has stated or what follows directly from it; do not assume facts that are not stated. The rule text and question
are context only; they are not evidence about the user.""",
    },
    # revision 1, after reading the v1 errors on the 60-utterance development subset: (A) conditions were split more
    # finely than the rule's own items, so answers given at the item level could not settle them, and loosely related
    # rule texts were declared irrelevant; (B) answers to questions that cover a condition were not used.
    "v2": {
        "A": """You formalise a rule text for one yes/no question. You see only the rule text and the question, not the
user's situation.
1. addresses_question: false only when the rule text concerns a different matter from the one the question asks about,
   so it could not answer the question whatever the facts; if the rule text bears on the question at all, true.
2. conditions: the yes/no statements about the user or the user's situation on which the rule text makes the answer
   depend, in the rule's own words, ids c1, c2, ... Give one condition per listed item or per clause of the rule text;
   do not split a single item or clause into finer parts (alternatives named inside one item stay together).
3. formula: a Boolean formula over the condition ids with and, or, not and parentheses that is true exactly when the
   answer to the question is yes according to the rule text.
If addresses_question is false, give no conditions and the formula "false".""",
        "B": """You check conditions about a user against what the user has told us: a scenario and a history of follow-up
questions with the user's yes/no answers. For each condition give:
- true: the scenario or history establishes that it holds;
- false: the scenario or history establishes that it does not hold;
- unresolved: neither settles it.
With every true or false verdict give an exact quotation, copied character for character, of the words that settle it:
a sentence or phrase of the scenario, or a whole history line ("Q: ... A: ...") when the user's answer to a follow-up
question settles it; a question may ask the condition itself, its opposite, or a part or rewording of it, and settles
it whenever the answer logically does. For unresolved give an empty quote. Use only what the user has stated or what
clearly follows from it; do not assume facts that are not stated. The rule text and question are context only; they
are not evidence about the user.""",
    },
    # revision 2 (last), after reading the v2 errors on the same 60: (A) conditions the question already presupposes
    # (for example who the rule addresses) were added and stayed open; (B) quotations sometimes carried the SCENARIO
    # label and so were not admitted.
    "v3": {
        "A": """You formalise a rule text for one yes/no question. You see only the rule text and the question, not the
user's situation.
1. addresses_question: false only when the rule text concerns a different matter from the one the question asks about,
   so it could not answer the question whatever the facts; if the rule text bears on the question at all, true.
2. conditions: the yes/no statements about the user or the user's situation that the rule text states as requirements,
   exclusions or alternatives for the answer, in the rule's own words, ids c1, c2, ... Give one condition per listed
   item or per clause of the rule text; do not split a single item or clause into finer parts (alternatives named
   inside one item stay together). Do not add conditions that the question already presupposes or that only describe
   whom the rule text addresses.
3. formula: a Boolean formula over the condition ids with and, or, not and parentheses that is true exactly when the
   answer to the question is yes according to the rule text.
If addresses_question is false, give no conditions and the formula "false".""",
        "B": """You check conditions about a user against what the user has told us: a scenario and a history of follow-up
questions with the user's yes/no answers. For each condition give:
- true: the scenario or history establishes that it holds;
- false: the scenario or history establishes that it does not hold;
- unresolved: neither settles it.
With every true or false verdict give an exact quotation, copied character for character from the scenario text or
from one history line, of the words that settle it (no section labels, no rewording): a sentence or phrase of the
scenario, or a whole history line ("Q: ... A: ...") when the user's answer to a follow-up question settles it; a
question may ask the condition itself, its opposite, or a part or rewording of it, and settles it whenever the answer
logically does. For unresolved give an empty quote. Use only what the user has stated or what clearly follows from it;
do not assume facts that are not stated. The rule text and question are context only; they are not evidence about the
user.""",
    },
}

A_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["addresses_question", "conditions", "formula"],
            "properties": {
                "addresses_question": {"type": "boolean"},
                "conditions": {"type": "array", "items": {
                    "type": "object", "additionalProperties": False, "required": ["id", "statement"],
                    "properties": {"id": {"type": "string"}, "statement": {"type": "string"}}}},
                "formula": {"type": "string"}}}

B_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["judgments"],
            "properties": {"judgments": {"type": "array", "items": {
                "type": "object", "additionalProperties": False, "required": ["id", "verdict", "quote"],
                "properties": {"id": {"type": "string"},
                               "verdict": {"type": "string", "enum": ["true", "false", "unresolved"]},
                               "quote": {"type": "string"}}}}}}


class FormulaError(ValueError):
    pass


def parse(formula, ids):
    """Formula string -> AST of ('var', id) | ('const', bool) | ('not', x) | ('and'|'or', [xs]). No eval."""
    toks = re.findall(r"\(|\)|[A-Za-z_][A-Za-z0-9_]*|&&|\|\||!|\S", formula)
    pos = 0

    def peek():
        return toks[pos].lower() if pos < len(toks) else None

    def take():
        nonlocal pos
        pos += 1
        return toks[pos - 1]

    def expr():
        xs = [term()]
        while peek() in ("or", "||"):
            take()
            xs.append(term())
        return xs[0] if len(xs) == 1 else ("or", xs)

    def term():
        xs = [factor()]
        while peek() in ("and", "&&"):
            take()
            xs.append(factor())
        return xs[0] if len(xs) == 1 else ("and", xs)

    def factor():
        t = peek()
        if t in ("not", "!"):
            take()
            return ("not", factor())
        if t == "(":
            take()
            x = expr()
            if peek() != ")":
                raise FormulaError("missing )")
            take()
            return x
        if t in ("true", "false"):
            take()
            return ("const", t == "true")
        if t is None:
            raise FormulaError("unexpected end")
        tok = take()
        if tok not in ids:
            raise FormulaError(f"unknown token {tok!r}")
        return ("var", tok)

    ast = expr()
    if pos != len(toks):
        raise FormulaError(f"trailing tokens {toks[pos:]}")
    return ast


def ev(ast, val):
    """Two-valued evaluation (val: id -> bool)."""
    k = ast[0]
    if k == "var":
        return val[ast[1]]
    if k == "const":
        return ast[1]
    if k == "not":
        return not ev(ast[1], val)
    vs = [ev(x, val) for x in ast[1]]
    return all(vs) if k == "and" else any(vs)


def kleene(ast, nu):
    """Strong Kleene evaluation; None = unknown."""
    k = ast[0]
    if k == "var":
        return {"true": True, "false": False}.get(nu.get(ast[1]))
    if k == "const":
        return ast[1]
    if k == "not":
        v = kleene(ast[1], nu)
        return None if v is None else not v
    vs = [kleene(x, nu) for x in ast[1]]
    if k == "and":
        return False if False in vs else (None if None in vs else True)
    return True if True in vs else (None if None in vs else False)


def variables(ast):
    if ast[0] == "var":
        return {ast[1]}
    if ast[0] == "const":
        return set()
    if ast[0] == "not":
        return variables(ast[1])
    return set().union(*(variables(x) for x in ast[1]))


def exact(ast, nu):
    """Exact deferral: enumerate every true/false completion of the unresolved conditions."""
    base = {g: v == "true" for g, v in nu.items() if v in ("true", "false")}
    open_ = sorted(g for g in variables(ast) if g not in base)
    results = set()
    for bits in itertools.product([False, True], repeat=len(open_)):
        results.add(ev(ast, {**base, **dict(zip(open_, bits))}))
        if len(results) == 2:
            return None
    return results.pop()


def decide(value):
    return {True: "Yes", False: "No", None: "Inquire"}[value]


def call_a(u, version):
    return llm.call(system=CP_PROMPTS[version]["A"], user=f"RULE TEXT:\n{u['snippet']}\n\nQUESTION:\n{u['question']}",
                    schema=A_SCHEMA, schema_name="rule_formalisation", run=0,
                    tag={"exp": "sharc-pilot", "method": f"cp-{version}-A", "case": h(u["snippet"], u["question"])})


def reading(u, conds, version, run):
    listing = "\n".join(f"{c['id']}: {c['statement']}" for c in conds)
    r = llm.call(system=CP_PROMPTS[version]["B"], user=case_block(u) + "\n\nCONDITIONS:\n" + listing, schema=B_SCHEMA,
                 schema_name="condition_reading", run=run,
                 tag={"exp": "sharc-pilot", "method": f"cp-{version}-B{run + 1}", "case": u["utterance_id"]})
    if not r["result"]:
        return None, r["error"]
    rows = {}
    for j in r["result"]["judgments"]:
        rows.setdefault(j["id"], j)
    facts, nu, raw = facts_text(u), {}, {}
    for c in conds:
        j = rows.get(c["id"])
        v = j["verdict"] if j else "unresolved"
        raw[c["id"]] = v
        if v in ("true", "false") and not (j["quote"].strip() and match.contains(facts, j["quote"])):
            v = "unresolved"  # quotation not found in scenario/history after normalisation: not admitted
        nu[c["id"]] = v
    return {"admitted": nu, "raw": raw, "quotes": {g: (rows.get(g) or {}).get("quote", "") for g in nu}}, None


def run_cp(u, version):
    a = call_a(u, version)
    if not a["result"]:
        return {"decision": None, "error": f"A: {a['error']}"}
    A = a["result"]
    out = {"A": A}
    if not A["addresses_question"]:
        out.update(decision="Irrelevant", kleene="Irrelevant", single="Irrelevant")
        return out
    conds = [c for c in A["conditions"] if c["id"]]
    try:
        ast = parse(A["formula"], {c["id"] for c in conds})
    except FormulaError as e:
        out.update(decision="Inquire", kleene="Inquire", single="Inquire", formula_error=str(e))
        return out
    b1, e1 = reading(u, conds, version, 0)
    b2, e2 = reading(u, conds, version, 1)
    if b1 is None:
        out.update(decision=None, error=f"B1: {e1}")
        return out
    nu = {g: (v if v in ("true", "false") and b2 is not None and b2["admitted"].get(g) == v else "unresolved")
          for g, v in b1["admitted"].items()}
    out.update(B1=b1, B2=b2, judgments=nu, decision=decide(exact(ast, nu)), kleene=decide(kleene(ast, nu)),
               single=decide(exact(ast, b1["admitted"])))
    return out


# ---------------------------------------------------------------- driver

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data")
    ap.add_argument("--ids", choices=["dev60", "all"], required=True)
    ap.add_argument("--designs", default="cp")
    ap.add_argument("--cp-version", default="v1")
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()
    assert Path(args.data).name == "sharc_train.json", "train split only; the dev split is reserved"
    sample = json.loads((OUT / "sample_ids.json").read_text())
    want = set(sample["dev60"] if args.ids == "dev60" else sample["order"])
    data = {r["utterance_id"]: r for r in json.loads(Path(args.data).read_text()) if r["utterance_id"] in want}
    assert len(data) == len(want)
    designs = args.designs.split(",")
    if "cp" in designs:  # call A once per (snippet, question) before the readings, so it is never paid twice
        uniq = {}
        for u in data.values():
            uniq.setdefault((u["snippet"], u["question"]), u)
        with ThreadPoolExecutor(args.workers) as ex:
            list(ex.map(lambda u: call_a(u, args.cp_version), uniq.values()))
    for d in designs:
        name = f"cp-{args.cp_version}" if d == "cp" else d
        path = OUT / f"results_{name}.json"
        res = json.loads(path.read_text()) if path.exists() else {}
        todo = [u for k, u in sorted(data.items()) if k not in res or res[k].get("decision") is None]
        fn = {"cp": lambda u: run_cp(u, args.cp_version), "direct": run_direct, "steps": run_steps, "sc3": run_sc3}[d]
        with ThreadPoolExecutor(args.workers) as ex:
            futs = {ex.submit(fn, u): u["utterance_id"] for u in todo}
            for f in as_completed(futs):
                try:
                    res[futs[f]] = f.result()
                except llm.BudgetExceeded as e:
                    print("STOP:", e, flush=True)
                    break
        for k, u in data.items():
            if k in res:
                res[k]["gold"] = label(u["answer"])
        path.write_text(json.dumps(res, ensure_ascii=False, indent=0, sort_keys=True) + "\n")
        sub = [res[k] for k in data if k in res]
        acc = sum(r.get("decision") == r["gold"] for r in sub) / max(1, len(sub))
        print(f"{name}: n={len(sub)} acc={acc:.3f} errors={sum(r.get('decision') is None for r in sub)} "
              f"spent={llm.spent():.4f}", flush=True)


if __name__ == "__main__":
    main()
