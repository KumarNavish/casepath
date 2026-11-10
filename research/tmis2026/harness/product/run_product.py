"""Headless adapter pieces shared by run_api.py (the entry point the paper uses): the caching, cost-recording model
transport and the mapping of the product's result to the harness plan format.

Product: a read-only worktree of casepath-internal at commit 7ff7af648279e58765732ab2e1ed8f36d7f3b155
(branch claude/casepath-internal-20261027), package `casepath` (`python -m casepath ...`). Override with
CASEPATH_PRODUCT=<worktree>. This module imports nothing from the product; run_api.load_product does, and checks that
every imported module lies inside that worktree.

The model is the product's own chat-completions connector (`casepath.agents.chat_model.ChatCompletionsModel`,
provider "databricks" path) pointed at OpenRouter's chat route; the container's proxy injects the credential, the
connector sends "Authorization: Bearer proxy-injected". A caching httpx transport keys every request by
sha256(url, body, run) so a rerun of the same claim-run is free; only 200 answers are cached. Every paid call is
written to runs/product/ledger_dev_<model>.jsonl with the provider's token counts and cost (usage.cost).

Mapping of the product's result to the plans the scorers read. Two views are recorded for every claim-run:
- `plan` (CONSERVATIVE, the primary view): every need in the evaluated checklist counts, whoever put it there.
  requests = needs with required "yes" and status "missing" or "unusable" -- workflow needs AND needs the process
  builder added on its own and marked required (the product shows both to the case worker as documents to obtain).
  An added need has its own id, so against the reference it is an unnecessary request unless the reference requires
  a document with that id. holds = needs with required "depends" (workflow or added; added ones are spurious holds).
  Suggested and optional rows are never requests.
- `plan_workflow_only`: the same, restricted to the workflow's own document needs (the earlier mapping).
Common to both:
- deferred (whole claim handed over): routing did not select a workflow (unmapped / needs_facts / ambiguous / fallback).
- family: the routed workflow id.
- A document whose step lies beyond the point where the walk waits is NOT in the checklist and is NOT a hold
  (the product names the step's question, not the document): it scores as missed / silent skip.
- questions: `waiting_for` facts, unmet-condition facts and the condition facts of "depends" rows.
- a failed run (status failed) -> plan None, scored as an empty plan (as for every arm).
- product_extra: needs the process builder added (title, step, statute article or not, required / suggested, status),
  present / unusable judgments, conflicting facts, facts by status, waiting_for, current step, outcome, answer, reply
  clause count, routing decision, warnings.
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from pathlib import Path

import httpx

PRODUCT_ROOT = Path(os.environ.get("CASEPATH_PRODUCT", "/home/user/work/casepath-product-7ff7af64"))
PRODUCT_COMMIT = "7ff7af648279e58765732ab2e1ed8f36d7f3b155"
HERE = Path(__file__).resolve().parent
TMIS = HERE.parents[1]
RUNS = TMIS / "runs" / "product"
CACHE = RUNS / "cache"
PRICES = {"gpt-6-luna": (0.10, 0.50), "gpt-6.1-terra": (1.00, 5.00)}  # USD per million tokens, OpenRouter list
_lock = threading.Lock()


class CachingTransport(httpx.BaseTransport):
    """Answers a request from the cache when the same (url, body, run) was answered before; otherwise forwards it
    through the container's proxy and records cost in the dev ledger."""

    def __init__(self, model: str, run: int, case_id: str, arm: str | None = None):
        self.model, self.run, self.case_id, self.arm = model, run, case_id, arm
        proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
        self.inner = httpx.HTTPTransport(proxy=proxy, verify="/root/.ccr/ca-bundle.crt", retries=2)
        CACHE.mkdir(parents=True, exist_ok=True)
        self.ledger = RUNS / f"ledger_dev_{model}.jsonl"

    def handle_request(self, request):
        body = request.read()
        key = hashlib.sha256(str(request.url).encode() + b"\0" + body + b"\0" + str(self.run).encode()).hexdigest()
        path = CACHE / f"{key}.json"
        if path.exists():
            saved = json.loads(path.read_text())
            return httpx.Response(200, content=saved["body"].encode(), headers={"content-type": "application/json"}, request=request)
        response = self.inner.handle_request(request)
        content = response.read()
        if response.status_code == 200:
            try:
                usage = json.loads(content).get("usage") or {}
            except ValueError:
                usage = {}
            cost = usage.get("cost")
            row = {"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "model": self.model, "case": self.case_id,
                   "run": self.run, "key": key, "input_tokens": usage.get("prompt_tokens"),
                   "cached_tokens": (usage.get("prompt_tokens_details") or {}).get("cached_tokens"),
                   "output_tokens": usage.get("completion_tokens"),
                   "usd": cost if cost is not None else _list_price(self.model, usage),
                   **({"arm": self.arm} if self.arm else {})}
            with _lock:
                path.write_text(json.dumps({"body": content.decode()}))
                with self.ledger.open("a") as f:
                    f.write(json.dumps(row) + "\n")
        return httpx.Response(response.status_code, content=content, headers=response.headers, request=request)


def _list_price(model, usage):
    pin, pout = PRICES.get(model, (0, 0))
    return ((usage.get("prompt_tokens") or 0) * pin + (usage.get("completion_tokens") or 0) * pout) / 1e6


def spent(model: str) -> float:
    path = RUNS / f"ledger_dev_{model}.jsonl"
    if not path.exists():
        return 0.0
    return sum(json.loads(line)["usd"] or 0 for line in path.read_text().splitlines() if line.strip())


def to_plan(outcome: dict, catalogue) -> dict:
    result = outcome.get("result") or {}
    usage = result.get("usage", [])
    calls = len(usage)
    if outcome["status"] != "completed":
        return {"plan": None, "plan_workflow_only": None, "status": "failed", "error": outcome.get("error"), "calls": calls,
                "usage": usage, "product_extra": {}}
    routing = outcome.get("routing") or {}
    if outcome.get("workflow") is None:
        plan = {"family": None, "requests": [], "holds": [], "questions": [], "deferred": True,
                "deferral_reason": f"routing {routing.get('status')}"}
        return {"plan": plan, "plan_workflow_only": dict(plan), "status": "completed", "calls": calls, "usage": usage,
                "product_extra": {"routing": {k: routing.get(k) for k in ("status", "needs", "candidates")}}}
    family = outcome["workflow"]["id"]
    template_docs = {d["id"] for d in catalogue.get(family)["documents"]}
    ev = result["evaluation"]
    requests, holds, on_file, extra_rows = [], [], [], []
    added_requests, added_holds = [], []
    questions = set(w["fact"] for w in ev["waiting_for"]) | {u["fact"] for u in ev.get("unmet", [])}
    for row in ev["documents"]:
        mine = row["document"] in template_docs
        if not mine:
            extra_rows.append(row)
        if row["required"] == "yes" and row["status"] in {"missing", "unusable"}:
            (requests if mine else added_requests).append(row["document"])
        elif row["required"] == "depends":
            (holds if mine else added_holds).append(row["document"])
            questions |= set(row.get("condition_facts") or [])
        if row["status"] == "present" and mine:
            on_file.append(row["document"])
    edits = {e["id"]: e for e in result.get("agent_edits", [])}
    added = []
    for row in extra_rows:
        definition = next((d for d in result["process"]["documents"] if d["id"] == row["document"]), {})
        edit = edits.get(definition.get("edit"), {})
        added.append({"id": row["document"], "title": row["title"], "step": row["step"], "required": row["required"],
                      "status": row["status"], "legal_basis": definition.get("legal_basis"),
                      "knowledge": definition.get("knowledge"), "by_agent": bool(edit), "reason": edit.get("reason")})
    facts = result.get("facts", [])
    extra = {
        "routing": {"status": routing.get("status"), "facts": [{k: f.get(k) for k in ("fact", "value")} for f in routing.get("facts", [])]},
        "agent_added_needs": added,
        "agent_questions": [e["args"].get("question") for e in result.get("agent_edits", []) if e["op"] == "add_question"],
        "agent_steps": [e["args"].get("title") for e in result.get("agent_edits", []) if e["op"] == "add_step"],
        "document_judgments": {d["document"]: {"status": d["status"], "verdict": d.get("verdict"), "shows": d.get("shows")}
                               for d in result.get("documents", [])},
        "facts": {f["fact"]: {"status": f["status"], "value": f.get("value"), "verdict": f.get("verdict"), "by": f.get("by"),
                              **({"second_value": f["second_value"]} if "second_value" in f else {}),
                              **({"presumed": f["presumed"]} if "presumed" in f else {}),
                              "cited": bool(f.get("citations"))} for f in facts},
        "conflicting_facts": [f["fact"] for f in facts if f["status"] == "conflicting"],
        "rejected_facts": [f["fact"] for f in facts if f.get("verdict") == "rejected"],
        "waiting_for": [w["fact"] for w in ev["waiting_for"]],
        "current_step": (ev.get("current") or {}).get("step"), "outcome": (ev.get("outcome") or {}).get("id"),
        "reached": ev.get("reached") or [r["step"] for r in ev.get("path", [])], "on_file": on_file,
        "deferral": ev.get("deferral"),
        "answer": result.get("answer"), "reply_clauses": len((result.get("reply") or {}).get("clauses", [])),
        "warnings": result.get("warnings"),
    }
    base = {"family": family, "questions": sorted(questions), "deferred": False}
    workflow_only = {**base, "requests": sorted(requests), "holds": sorted(holds)}
    conservative = {**base, "requests": sorted(requests + added_requests), "holds": sorted(holds + added_holds),
                    "added_requests": sorted(added_requests), "added_holds": sorted(added_holds)}
    return {"plan": conservative, "plan_workflow_only": workflow_only, "status": "completed", "calls": calls, "usage": usage,
            "product_extra": extra}
