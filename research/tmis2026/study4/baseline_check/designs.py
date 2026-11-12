"""Study 4 step 1 (fair-baseline check): the two hold-capable designs, built from Study 3's own material.

POST HOC, development data (Study 3's fresh2 is development data from now on; study4/SPEC.md).

A  "Prompt with hold option" (key hold_prompt): Rules in context's material unchanged (tenancy: POLICY_V2 + the
   fresh2 rule packs with their silence clause, harness/v2/tenancy_v2.system_v2; theft: POLICY + source passages +
   catalogue + the reviewed rules, the CP4 harness's Rpack system), with the task replaced by prompts/A_*_task.txt:
   explicit three-way decision per document, the silence rule, and the stop / hold rules of the defining event in plain
   words. Tenancy output: Rules in context's own schema and parser (tenancy_methods.B1_SCHEMA, _plan_from_decisions,
   decisions request / hold / not_needed / on_file). Theft output: one row per catalogue document with decision
   request / hold / not_needed (the checklist-row format of Study 3's ReAct theft arm), parsed to the requests / holds
   lists every theft design stores (catalogue names, as theft_methods._ids).
B  "Model executes rules with hold option" (key mer_hold): Study 3's design unchanged (harness/product/baselines.py
   col_material / run_col request; baselines_theft.py theft_material / COL_TASK / col_schema), on gpt-6.1-terra. Both
   stored tasks already state the hold rule (tenancy: "hold if its applicability is unresolved", completions; theft:
   "one needed under some but not all is held"), so no sentence is added.

Every call goes through harness/llm.py's caching client (request body identical to the one baselines.chat sends),
with the cache and the ledgers redirected to study4/baseline_check/runs/ (one ledger per model).
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
TMIS = HERE.parents[1]
RUNS = HERE / "runs"
PROMPTS = HERE / "prompts"
for p in (TMIS / "harness" / "product", TMIS / "harness", TMIS / "harness" / "v2"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
os.environ.setdefault("TMIS_MODEL", "openai/gpt-6-luna")  # bound by llm at import; every call names its model

import common  # noqa: E402  (fresh2 guard; wraps llm.call with transport retries)
import llm  # noqa: E402

llm.CACHE = RUNS / "cache"
llm.LEDGER = RUNS / "ledger_UNSET.jsonl"  # set per batch by use_model(); nothing is written here
llm.BUDGET_USD = 1e9  # the cap is enforced by run.py over both ledgers

MODELS = {"luna": "gpt-6-luna", "terra": "gpt-6.1-terra"}
A_TEN_TASK = (PROMPTS / "A_tenancy_task.txt").read_text()
A_THEFT_TASK = (PROMPTS / "A_theft_task.txt").read_text()


def ledger(model):
    return RUNS / f"ledger_{model}.jsonl"


def use_model(model):
    llm.LEDGER = ledger(model)
    llm.LEDGER.parent.mkdir(parents=True, exist_ok=True)


def spent_total():
    tot = 0.0
    for m in MODELS.values():
        p = ledger(m)
        if p.exists():
            tot += sum(float(json.loads(x).get("cost") or 0) for x in p.read_text().splitlines() if x.strip())
    return tot


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


# ----------------------------------------------------------------------------------------------- material
class Material:
    """All prompts of both designs for one data set ('fresh' for format checks, 'fresh2' for the run)."""

    def __init__(self, data):
        import tenancy_methods as s1
        import tenancy_v2 as t2
        import baselines as B
        import baselines_theft as BT
        self.data = data
        self.Dten = common.data("tenancy", data)
        self.Dth = common.data("theft", data)
        self.T = self.Dth.texts()
        self.s1, self.t2 = s1, t2
        pack = t2.pack_for(self.Dten)
        # A tenancy: Rules in context's system with the task replaced
        self.ric_ten_system = t2.system_v2(t2.B1V2_TASK, pack)
        self.a_ten_system = t2.system_v2(A_TEN_TASK, pack)
        assert self.a_ten_system.replace(A_TEN_TASK, t2.B1V2_TASK) == self.ric_ten_system
        # B tenancy: Study 3's COL material, data module as the Study 3 worker sets it (B.F = D)
        B.F = self.Dten
        self.b_ten_system, self.b_ten_schema, self.b_ten_to_plan, _cb = B.col_material()
        # theft: the Rules-in-context base (POLICY + passages + catalogue + reviewed rules)
        tm, system, base = BT.theft_material()
        self.tm, self.base = tm, base
        self.ric_theft_system = base + "\n\n" + tm.PLAN_TASK
        self.a_theft_system = base + "\n\n" + A_THEFT_TASK
        self.a_theft_schema = tm.obj({"documents": tm.arr(tm.obj({"document": tm.DOC_ENUM,
                                                                  "decision": {"type": "string", "enum": ["request", "hold", "not_needed"]}}), 40),
                                      "questions": tm.arr(tm.TEXT, 10)})
        self.b_theft_system = base + "\n\n" + BT.COL_TASK
        self.b_theft_schema = BT.col_schema(tm, system)

    def cases(self, regime):
        return list(self.Dten.claim_ids("test")) if regime == "tenancy" else sorted(self.T)

    def prompts(self):
        """Every system prompt and schema a design sends (the user message is the case only)."""
        return {"A_tenancy_system": self.a_ten_system, "A_tenancy_schema": json.dumps(self.s1.B1_SCHEMA, sort_keys=True),
                "A_theft_system": self.a_theft_system, "A_theft_schema": json.dumps(self.a_theft_schema, sort_keys=True),
                "B_tenancy_system": self.b_ten_system, "B_tenancy_schema": json.dumps(self.b_ten_schema, sort_keys=True),
                "B_theft_system": self.b_theft_system, "B_theft_schema": json.dumps(self.b_theft_schema, sort_keys=True)}

    # ------------------------------------------------------------------------------------------- calls
    def call(self, design, regime, case, run, model, tag_method):
        tag = {"exp": "s4-baseline-check", "method": tag_method, "case": case, "data": self.data}
        if regime == "tenancy":
            user = self.t2.case_block(self.Dten, case)
            if design == "A":
                r = llm.call(system=self.a_ten_system, user=user, schema=self.s1.B1_SCHEMA, schema_name="evidence_plan",
                             run=run, tag=tag, model="openai/" + model)
                plan = self.s1._plan_from_decisions(r["result"], "documents") if r["result"] else None
            else:
                r = llm.call(system=self.b_ten_system, user=user, schema=self.b_ten_schema, schema_name="executed_plan",
                             run=run, tag=tag, model="openai/" + model)
                plan = self.b_ten_to_plan(r["result"], "plan") if r["result"] else None
        else:
            user = "CASE:\n" + self.T[case]["text"]
            if design == "A":
                r = llm.call(system=self.a_theft_system, user=user, schema=self.a_theft_schema, schema_name="checklist",
                             run=run, tag=tag, model="openai/" + model)
                plan = self.theft_rows_to_plan(r["result"]) if r["result"] else None
            else:
                r = llm.call(system=self.b_theft_system, user=user, schema=self.b_theft_schema, schema_name="executed_plan",
                             run=run, tag=tag, model="openai/" + model, max_tokens=6000)
                res = r["result"]
                plan = self.tm._ids({k: res[k] for k in ("requests", "holds", "questions")}) if res else None
        return {"plan": plan, "error": r.get("error"), "cached": r.get("cached"), "usage_cost": (r.get("usage") or {}).get("cost"),
                "raw": r.get("result")}

    def theft_rows_to_plan(self, res):
        """Catalogue IDs -> catalogue names (theft_methods.INV, as _ids); a document listed as request anywhere is a
        request; hold only if never requested."""
        inv = self.tm.INV
        req = {inv[x["document"]] for x in res["documents"] if x["decision"] == "request"}
        hold = {inv[x["document"]] for x in res["documents"] if x["decision"] == "hold"} - req
        return {"requests": sorted(req), "holds": sorted(hold), "questions": res.get("questions", [])}
