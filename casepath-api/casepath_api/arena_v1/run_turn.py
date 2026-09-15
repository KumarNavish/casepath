"""Answer every pending request of one arena turn through the OpenRouter transport (parallel workers)."""
from __future__ import annotations

import argparse, concurrent.futures, json, time
from pathlib import Path

from casepath_api.arena_v1 import transport


def answer(entry: dict, model: str, max_tokens: int, temperature: float, provider_only) -> dict:
    d = Path(entry["dir"])
    if (d / "answer.json").exists():
        return {"dir": entry["dir"], "status": "already_answered"}
    messages = [{"role": "system", "content": (d / "system.txt").read_text()}, {"role": "user", "content": (d / "user.json").read_text()}]
    result = transport.call_with_transport_retry(messages, model=model, max_tokens=max_tokens, temperature=temperature, provider_only=provider_only)
    receipt = {k: v for k, v in result.items() if k != "content"}
    receipt["request_dir"] = entry["dir"]; receipt["arms"] = entry["arms"]; receipt["case"] = entry["case"]
    (d / "receipt.json").write_text(json.dumps(receipt, indent=1, ensure_ascii=False))
    if result["ok"]:
        (d / "answer.json").write_text(result["content"])
        return {"dir": entry["dir"], "status": "answered", "cost_usd": result.get("cost_usd"), "tokens": result.get("usage", {}).get("total_tokens")}
    (d / "failure.json").write_text(json.dumps(receipt, indent=1))
    return {"dir": entry["dir"], "status": "transport_failure", "error": result.get("error")}


def main() -> None:
    ap = argparse.ArgumentParser(); ap.add_argument("--run", required=True); ap.add_argument("--turn", type=int, required=True)
    ap.add_argument("--model", required=True); ap.add_argument("--max-tokens", type=int, default=8000); ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--provider-only", default="anthropic"); ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()
    listing = json.loads((Path(a.run) / "pending" / f"turn-{a.turn}" / "LISTING.json").read_text())
    provider_only = [p for p in a.provider_only.split(",") if p] or None
    started = time.time(); results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=a.workers) as pool:
        for r in pool.map(lambda e: answer(e, a.model, a.max_tokens, a.temperature, provider_only), listing):
            results.append(r)
    lengths = []
    for e in listing:
        rp = Path(e["dir"]) / "receipt.json"
        if rp.exists():
            rr = json.loads(rp.read_text())
            if rr.get("finish_reason") == "length":
                lengths.append(e["dir"].split("/pending/")[1])
    summary = {"turn": a.turn, "model": a.model, "max_tokens": a.max_tokens, "truncated": lengths, "requests": len(listing), "answered": sum(r["status"] == "answered" for r in results),
               "already": sum(r["status"] == "already_answered" for r in results), "failures": [r for r in results if r["status"] == "transport_failure"],
               "cost_usd": round(sum((r.get("cost_usd") or 0) for r in results), 6), "wall_s": round(time.time() - started, 1)}
    (Path(a.run) / "pending" / f"turn-{a.turn}" / "TRANSPORT_SUMMARY.json").write_text(json.dumps(summary, indent=1))
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
