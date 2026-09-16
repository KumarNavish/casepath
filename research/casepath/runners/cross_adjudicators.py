"""Frozen cross-family reference adjudication from ADJUDICATOR_ROBUSTNESS_PROTOCOL.md."""
from __future__ import annotations

import concurrent.futures as cf
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
API = ROOT / "casepath-api"
sys.path.insert(0, str(API))
from casepath_api.arena_v1 import transport

ART = ROOT / "research/casepath/artifacts"
PROMPT = ROOT / "research/casepath/prompts/reference_adjudication_system.txt"
CONTRACT = ROOT / "research/casepath/reference_contracts/rent_increase.json"
MODELS = {
    "opus5": "anthropic/claude-opus-5",
    "gemini31pro": "google/gemini-3.1-pro-preview",
    "deepseekv4pro": "deepseek/deepseek-v4-pro",
}
REPEATS = (1, 2, 3)
MAX_WORKERS = 18

def body(contract, text: str) -> str:
    parts = ["CASE NARRATIVE:", text[:9200], "", "DECISIONS:"]
    for d in contract["decisions"]:
        parts += [
            f'\n[{d["decision_id"]}] {d["must_determine"][:260]}',
            f'  live_when: {d["live_when"]}',
            f'  dead_when: {d["dead_when"]}',
        ]
    return "\n".join(parts)


def parse_json(content: str):
    try:
        value = json.loads(content)
    except Exception:
        m = re.search(r"\{.*\}", content, re.S)
        if not m:
            return None, "unparseable"
        try:
            value = json.loads(m.group(0))
        except Exception:
            return None, "unparseable"
    ds = value.get("decisions") if isinstance(value, dict) else None
    if not isinstance(ds, list):
        return None, "missing decisions"
    return ds, None

def run_one(job, system, contract):
    tag, model, unit, k = job
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": body(contract, unit["text"]) + f"\n\n(adjudicator {k})"},
    ]
    result = transport.call_with_transport_retry(
        messages, model=model, max_tokens=8000, temperature=0.0,
        provider_only=None, timeout=240.0,
    )
    decisions, parse_error = (None, None)
    if result.get("ok"):
        decisions, parse_error = parse_json(result.get("content") or "")
    return {
        "unit_id": unit["unit_id"], "claim_id": unit["claim_id"],
        "scenario": unit["scenario"], "arm_case": unit["arm_case"],
        "adjudicator_tag": tag, "requested_model": model, "repeat": k,
        "ok": bool(result.get("ok") and decisions is not None),
        "decisions": decisions, "parse_error": parse_error,
        "response_model": result.get("model"), "provider": result.get("provider"),
        "generation_id": result.get("generation_id"), "usage": result.get("usage"),
        "cost_usd": result.get("cost_usd"), "latency_s": result.get("latency_s"),
        "payload_sha256": result.get("payload_sha256"), "attempts": result.get("attempts"),
        "transport_error": None if result.get("ok") else result.get("error"),
    }

def main():
    os.environ.setdefault(
        "CASEPATH_OPENROUTER_KEY_FILE",
        str(Path.home() / ".config/casepath/openrouter.key"),
    )
    system = PROMPT.read_text()
    contract = json.loads(CONTRACT.read_text())
    units = json.loads((ART / "conf_cases.json").read_text())
    prompt_sha = hashlib.sha256(system.encode()).hexdigest()
    contract_sha = hashlib.sha256(CONTRACT.read_bytes()).hexdigest()
    jobs = [(tag, model, u, k) for tag, model in MODELS.items() for u in units for k in REPEATS]
    started = datetime.now(timezone.utc).isoformat()
    results = []
    with cf.ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futs = [ex.submit(run_one, j, system, contract) for j in jobs]
        for i, fut in enumerate(cf.as_completed(futs), 1):
            row = fut.result()
            results.append(row)
            if i % 20 == 0 or i == len(jobs):
                good = sum(r["ok"] for r in results)
                cost = sum(float(r.get("cost_usd") or 0) for r in results)
                print(f"{i}/{len(jobs)} complete; valid={good}; reported_cost=${cost:.4f}", flush=True)
    results.sort(key=lambda r: (r["adjudicator_tag"], r["unit_id"], r["repeat"]))
    packet = {
        "contract": "casepath.cross-adjudicator-run/1.0.0",
        "frozen_protocol": "research/casepath/ADJUDICATOR_ROBUSTNESS_PROTOCOL.md",
        "started_at": started, "finished_at": datetime.now(timezone.utc).isoformat(),
        "system_prompt_sha256": prompt_sha, "reference_contract_sha256": contract_sha,
        "models": MODELS, "temperature": 0.0, "max_tokens": 8000,
        "repeats_per_unit": 3, "unit_count": len(units), "rows": results,
    }
    out = ART / "cross_adjudicators_raw.json"
    out.write_text(json.dumps(packet, ensure_ascii=False, indent=1))
    failures = [r for r in results if not r["ok"]]
    cost = sum(float(r.get("cost_usd") or 0) for r in results)
    print(f"wrote {out}; valid={len(results)-len(failures)}/{len(results)}; reported_cost=${cost:.4f}")
    if failures:
        print("FAILED ROWS:")
        for r in failures[:30]:
            print(r["adjudicator_tag"], r["unit_id"], r["repeat"], r.get("parse_error") or r.get("transport_error"))
        raise SystemExit(2)

if __name__ == "__main__":
    main()
