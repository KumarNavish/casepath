"""Full cost accounting across every run and study that consumed provider calls."""
from __future__ import annotations

import argparse, json
from pathlib import Path


def run_cost(run: Path) -> dict:
    calls = cost = pin = pout = 0
    trunc = 0
    for rec in run.glob("pending/turn-*/*/*/receipt.json"):
        r = json.loads(rec.read_text())
        if not r.get("ok"):
            continue
        u = r.get("usage") or {}
        calls += 1; cost += r.get("cost_usd") or 0.0
        pin += u.get("prompt_tokens", 0); pout += u.get("completion_tokens", 0)
        trunc += r.get("finish_reason") == "length"
    return {"calls": calls, "cost_usd": round(cost, 4), "prompt_tokens": pin, "completion_tokens": pout, "truncated": trunc}


def main() -> None:
    ap = argparse.ArgumentParser(); ap.add_argument("--runs", nargs="*", default=[]); ap.add_argument("--studies", nargs="*", default=[]); ap.add_argument("--out", required=True)
    a = ap.parse_args()
    rows = {}
    for r in a.runs:
        p = Path(r); rows[p.parent.name + "/" + p.name] = run_cost(p)
    for s in a.studies:
        p = Path(s)
        if p.exists():
            d = json.loads(p.read_text())
            rows[p.stem] = {"calls": d.get("claims", d.get("episodes")), "cost_usd": d.get("cost_usd"), "note": "study"}
    total = round(sum((v.get("cost_usd") or 0) for v in rows.values()), 4)
    out = {"contract": "casepath.ctes-cost-accounting/1.0.0", "provider": "OpenRouter → Anthropic (allow_fallbacks=false)",
           "model": "anthropic/claude-opus-5", "temperature": 0.0, "max_output_tokens": 8000,
           "per_run": rows, "total_cost_usd": total,
           "total_calls": sum((v.get("calls") or 0) for v in rows.values() if v.get("note") != "study"),
           "note": "Zero-model control arms (constant, random, static-checklist, keyword-router, domain-compiler) cost nothing. "
                   "Episode writing and verification used separate provider calls recorded in their own artifacts."}
    Path(a.out).write_text(json.dumps(out, indent=1)); print(json.dumps({"total_cost_usd": total, "runs": {k: v.get("cost_usd") for k, v in rows.items()}}, indent=1))


if __name__ == "__main__":
    main()
