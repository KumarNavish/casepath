"""Headless adapter: run casepath-internal (unchanged, pinned commit) on one tenancy claim and map its result to the
harness plan format.

    run_product(case_text, attachments, catalogue_dir, model, run, case_id) -> {"plan": ..., "product_extra": ..., ...}

The product runs through its own entry point `casepath_internal.core.prepare`, on a fresh temporary case store per
claim-run (no Knowledge, no edits), with the job built exactly as the product's run service builds it
(`runner.RunService.job`). The model is the product's own chat-completions connector (`chat_model.ChatCompletionsModel`,
provider "databricks" path) pointed at OpenRouter's chat route; the container's proxy injects the credential, the
connector sends "Authorization: Bearer proxy-injected". A caching httpx transport keys every request by
sha256(url, body, run) so a rerun of the same claim-run is free; only 200 answers are cached. Every paid call is
written to runs/product/ledger_dev_<model>.jsonl with the provider's token counts and cost (usage.cost).
Transport errors and 429/5xx are retried by the connector itself (5 attempts); a failed run is retried once.

Mapping of the product's result to the plan the scorers read (conservative and symmetric):
- deferred (whole claim handed over): routing did not select a workflow (unmapped / needs_facts / ambiguous / fallback).
- family: the routed workflow id.
- requests: template document needs in the evaluated checklist with required "yes" and status "missing" or "unusable"
  (the product's `obtain` next actions for template documents).
- holds: template document needs in the checklist with required "depends" (their own condition is open; the row names
  the condition facts). A document whose step lies beyond the point where the walk waits is NOT in the checklist and
  is NOT a hold (the product names the step's question, not the document): it scores as missed / silent skip.
- on file: status "present". Suggested and optional rows are never requests.
- questions: `waiting_for` facts, unmet-condition facts and the condition facts of "depends" rows.
- a failed run (status failed) -> plan None, scored as an empty plan (as for every arm).
- product_extra: needs the process builder added (title, step, statute article or not, required / suggested, status),
  present / unusable judgments, conflicting facts, facts by status, waiting_for, current step, outcome, answer, reply
  clause count, routing decision, warnings. Agent-added needs are not in `requests`; scored separately.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import shutil
import sys
import tempfile
import threading
import time
from pathlib import Path

import httpx

PRODUCT = Path("/home/user/work/casepath-ui3/casepath-internal")
PRODUCT_COMMIT = "55b80304dadb8a2b2671568f37fb28a39e989bdb"
sys.path.insert(0, str(PRODUCT))

from casepath_internal import core  # noqa: E402
from casepath_internal.chat_model import ChatCompletionsModel  # noqa: E402
from casepath_internal.config import load_settings  # noqa: E402
from casepath_internal.extract import extract  # noqa: E402
from casepath_internal.store import CaseStore  # noqa: E402
from casepath_internal.workflows import Catalogue  # noqa: E402

HERE = Path(__file__).resolve().parent
TMIS = HERE.parents[1]
RUNS = TMIS / "runs" / "product"
CACHE = RUNS / "cache"
PRICES = {"gpt-6-luna": (0.10, 0.50), "gpt-6.1-terra": (1.00, 5.00)}  # USD per million tokens, OpenRouter list
_lock = threading.Lock()


class CachingTransport(httpx.BaseTransport):
    """Answers a request from the cache when the same (url, body, run) was answered before; otherwise forwards it
    through the container's proxy and records cost in the dev ledger."""

    def __init__(self, model: str, run: int, case_id: str):
        self.model, self.run, self.case_id = model, run, case_id
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
                   "usd": cost if cost is not None else _list_price(self.model, usage)}
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


def make_model(model: str, run: int, case_id: str):
    env = {"CASEPATH_MODEL_PROVIDER": "databricks", "CASEPATH_MODEL_ENDPOINT": "https://openrouter.ai",
           "CASEPATH_MODEL": model.split("/")[-1], "CASEPATH_MODEL_GATEWAY_HOSTS": "openrouter.ai",
           "CASEPATH_CHAT_PATH": "/api/v1/chat/completions", "CASEPATH_MODEL_API": "chat",
           "CASEPATH_CA_BUNDLE": "/root/.ccr/ca-bundle.crt", "CASEPATH_DATA_DIR": "/tmp/unused"}
    settings = load_settings(env).model
    return ChatCompletionsModel(settings, lambda: "proxy-injected", transport=CachingTransport(model, run, case_id))


def run_product(case_text: str, attachments: list[dict], catalogue_dir: Path, model: str = "gpt-6-luna", run: int = 0,
                case_id: str = "case", title: str | None = None, effort: str = "medium") -> dict:
    """attachments: [{"file_name", "media_type", "bytes"}]. Returns {"plan", "product_extra", "status", "error",
    "usage", "calls"}."""
    catalogue = Catalogue.load(catalogue_dir)
    data_dir = Path(tempfile.mkdtemp(prefix="cp-product-"))
    try:
        store = CaseStore(data_dir)
        case = store.create_case(title or "Tenancy claim", {}, "harness")
        files = [("message.txt", "text/plain", case_text.encode())] + [(a["file_name"], a["media_type"], a["bytes"]) for a in attachments]
        for name, media, data in files:
            row = extract(name, media, data)
            store.add_file(case["id"], name, row["media_type"], row["kind"], data, row, "harness")
        job = {"format": core.JOB, "case": store.get_case(case["id"]), "files": store.list_files(case["id"], with_text=True),
               "workflows": list(catalogue.workflows), "knowledge": [], "edits": [],
               "options": {"effort": effort, "read_scans": True, "reading_workers": 2, "page_image_side": 1700, "token_budget": None}}
        outcome = None
        for attempt in range(2):
            outcome = core.prepare(job, make_model(model, run, case_id), core.StoreBlobs(store))
            if outcome["status"] == "completed":
                break
        store.close()
    finally:
        shutil.rmtree(data_dir, ignore_errors=True)
    return to_plan(outcome, catalogue)


def to_plan(outcome: dict, catalogue) -> dict:
    result = outcome.get("result") or {}
    usage = result.get("usage", [])
    calls = len(usage)
    if outcome["status"] != "completed":
        return {"plan": None, "status": "failed", "error": outcome.get("error"), "calls": calls, "usage": usage, "product_extra": {}}
    routing = outcome.get("routing") or {}
    if outcome.get("workflow") is None:
        return {"plan": {"family": None, "requests": [], "holds": [], "questions": [], "deferred": True,
                         "deferral_reason": f"routing {routing.get('status')}"},
                "status": "completed", "calls": calls, "usage": usage,
                "product_extra": {"routing": {k: routing.get(k) for k in ("status", "needs", "candidates")}}}
    family = outcome["workflow"]["id"]
    template_docs = {d["id"] for d in catalogue.get(family)["documents"]}
    ev = result["evaluation"]
    requests, holds, on_file, extra_rows = [], [], [], []
    questions = set(w["fact"] for w in ev["waiting_for"]) | {u["fact"] for u in ev.get("unmet", [])}
    for row in ev["documents"]:
        if row["document"] not in template_docs:
            extra_rows.append(row)
            continue
        if row["required"] == "yes" and row["status"] in {"missing", "unusable"}:
            requests.append(row["document"])
        elif row["required"] == "depends":
            holds.append(row["document"])
            questions |= set(row.get("condition_facts") or [])
        if row["status"] == "present":
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
        "document_judgments": {d["document"]: {"status": d["status"], "verdict": d.get("verdict")} for d in result.get("documents", [])},
        "facts": {f["fact"]: {"status": f["status"], "value": f.get("value"), "verdict": f.get("verdict"), "by": f.get("by"),
                              **({"second_value": f["second_value"]} if "second_value" in f else {})} for f in facts},
        "conflicting_facts": [f["fact"] for f in facts if f["status"] == "conflicting"],
        "rejected_facts": [f["fact"] for f in facts if f.get("verdict") == "rejected"],
        "waiting_for": [w["fact"] for w in ev["waiting_for"]],
        "current_step": (ev.get("current") or {}).get("step"), "outcome": (ev.get("outcome") or {}).get("id"),
        "reached": ev.get("reached"), "on_file": on_file,
        "answer": result.get("answer"), "reply_clauses": len((result.get("reply") or {}).get("clauses", [])),
        "warnings": result.get("warnings"),
    }
    plan = {"family": family, "requests": sorted(requests), "holds": sorted(holds), "questions": sorted(questions),
            "deferred": False}
    return {"plan": plan, "status": "completed", "calls": calls, "usage": usage, "product_extra": extra}
