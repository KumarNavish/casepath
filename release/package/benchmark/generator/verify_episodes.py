"""Narrow semantic verification of arena episodes through an independent model family.

Checks only the properties the arms are scored on: (a) each motif-bound customer paragraph asserts the
motif semantics without claiming delivery, (b) each return paragraph carries its scope semantics
(partial visibly lacks an element, final establishes the facts, unavailable denies existence,
irrelevant is unrelated), (c) instruction paragraphs state the acceptable-evidence routes and the
"a party's account does not establish the record" rule. Narrative polish is out of scope.
"""
from __future__ import annotations

import argparse, concurrent.futures, json, re
from pathlib import Path

from casepath_api.arena_v1 import transport

SYSTEM = """You verify one synthetic benchmark episode. You receive brief.json (paragraph specifications) and texts.json (the written paragraphs). Check ONLY these decisive properties and ignore narrative style, prose quality and global date consistency:
1. For every customer paragraph that has a "motif" field, the text must assert that motif's semantics: possession_report = the customer states they HAVE/HOLD the record (and must NOT say they are sending, attaching or enclosing it); content_quote = the customer describes or quotes what the record says from memory (and must NOT say they hold or are sending it); third_party_relay = another party told them about the record by phone/verbally; promise_automatic = the holder will send it automatically; denial_nonexistent = no such record was ever produced; existence_only = the record exists somewhere without content or possession; conflict = two statements about the record disagree; ambiguous_reference = the reference could mean more than one catalogue record; stale_then_correct = an older version whose figures were later corrected.
2. Every paragraph whose id starts with "ret-" must carry its scope: "partial" visibly lacks a required element (and says so or is plainly incomplete); "partial_correcting" is an older version whose figures are later corrected; "final" establishes the stated facts with concrete values; "unavailable" is a written statement that no such record exists; "irrelevant" is unrelated to the facts under review.
3. Every instruction paragraph (id starts with "gov#") must state what must be established and which records are acceptable; at least one non-conditional instruction paragraph must state that a party's description, account or recollection of a record does not establish its content.
4. No paragraph may use the words attached/enclosed/beigelegt/beiliegend, and none may reveal whether a record will be adequate.
Return exactly one JSON object: {"ok": true|false, "problems": [{"id": "<paragraph id>", "rule": 1|2|3|4, "issue": "<short, quote the offending phrase>"}]}. Report only violations of rules 1-4. JSON only."""


def check(ep_dir: Path, model: str) -> dict:
    brief = json.loads((ep_dir / "brief.json").read_text()); texts = json.loads((ep_dir / "texts.json").read_text())
    spec = [{"id": p["id"], "kind": p.get("kind"), "motif": p.get("motif"), "scope": p.get("scope"), "must_convey": p.get("must_convey"), "must_not": p.get("must_not")} for p in brief["paragraphs"]]
    user = json.dumps({"language": brief["language"], "paragraph_specs": spec, "texts": texts}, ensure_ascii=False)
    r = transport.call_with_transport_retry([{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}], model=model, max_tokens=2000, temperature=0.0, provider_only=None)
    if not r["ok"]:
        return {"episode": ep_dir.name, "ok": None, "error": r.get("error", "")[:200]}
    txt = r["content"].strip()
    if txt.startswith("```"):
        txt = txt.strip("`").split("\n", 1)[1].rsplit("```", 1)[0]
    try:
        v = json.loads(txt)
    except Exception:
        return {"episode": ep_dir.name, "ok": None, "error": "unparsable verdict", "raw": txt[:300]}
    return {"episode": ep_dir.name, "ok": bool(v.get("ok")), "problems": v.get("problems", []), "cost_usd": r.get("cost_usd")}


def main() -> None:
    ap = argparse.ArgumentParser(); ap.add_argument("--data", required=True); ap.add_argument("--model", default="openai/gpt-5.6-terra"); ap.add_argument("--workers", type=int, default=10); ap.add_argument("--out", required=True)
    a = ap.parse_args(); dirs = sorted(p for p in (Path(a.data) / "gen").iterdir() if (p / "texts.json").exists())
    with concurrent.futures.ThreadPoolExecutor(max_workers=a.workers) as pool:
        results = list(pool.map(lambda d: check(d, a.model), dirs))
    summary = {"model": a.model, "episodes": len(results), "ok": sum(r.get("ok") is True for r in results), "failed_checks": sum(r.get("ok") is False for r in results),
               "errors": sum(r.get("ok") is None for r in results), "cost_usd": round(sum((r.get("cost_usd") or 0) for r in results), 4), "results": results}
    Path(a.out).write_text(json.dumps(summary, indent=1, ensure_ascii=False))
    print(json.dumps({k: summary[k] for k in ("model", "episodes", "ok", "failed_checks", "errors", "cost_usd")}))
    for r in results:
        if r.get("ok") is False:
            print(" ", r["episode"], [f"{p.get('id')}(r{p.get('rule')}): {str(p.get('issue'))[:90]}" for p in r["problems"]][:3])


if __name__ == "__main__":
    main()
