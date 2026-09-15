"""Write the natural-language paragraphs of arena episodes from their briefs, through the transport.

The writer model is deliberately from a different family than any evaluated arm model: the gold labels
never depend on wording, but a writer that shares idiosyncrasies with the solver would be a confound.
Every episode is validated mechanically (all brief paragraph ids present, no banned delivery words, no
catalogue document ids in the prose); a failing episode is rewritten at most twice with its problems fed
back, and every attempt is recorded in WRITE_RECEIPTS.json.
"""
from __future__ import annotations

import argparse, concurrent.futures, json, re
from pathlib import Path

from casepath_api.arena_v1 import transport

SYSTEM = """You are a careful bilingual (English / Swiss Standard German) writer producing the natural-language sources of ONE synthetic claim-handling episode for a research benchmark. You receive brief.json. It lists paragraphs with an id, a kind (customer | instruction | return) and must_convey / must_not semantics.

Write every paragraph as natural prose:
- kind=customer: the customer's own voice (first person), in the language given by brief.language ("de" = Swiss Standard German, using ss for ss, never the sharp s; "en" = English). 1-3 sentences each. Use concrete 2025 dates and party names where natural. A paragraph carrying a motif must assert that motif's semantics exactly: possession_report = the customer states they HOLD the record and must NOT say they are sending it; content_quote = the customer describes what the record says from memory and must NOT claim to hold or send it; third_party_relay = another party told them about it verbally; promise_automatic = the holder will send it by themselves; denial_nonexistent = no such record was ever produced; existence_only = it exists somewhere, with no content and no possession; conflict = two statements about it disagree; ambiguous_reference = the reference could mean more than one record; stale_then_correct = an older version whose figures were later corrected.
- kind=instruction: neutral handling guidance for the claims handler, ALWAYS in English, 1-3 sentences, precise about which records are acceptable and which are not. At least one non-conditional instruction paragraph must state in its own words that a party's description, account or recollection of a record does not establish its content. A conditional instruction must say that the obligation arises only once a returned record itself reports the triggering circumstance.
- kind=return (ids starting with ret-): the text of the returned record itself, in the episode language, 1-4 sentences, with concrete values and dates consistent with the customer paragraphs. scope=partial must visibly lack the stated element and say so; scope=partial_correcting is an older version whose figures were later corrected; scope=final must establish the stated fact(s) concretely; scope=irrelevant must be genuinely unrelated; scope=unavailable is a written statement that no such record exists.

Hard rules: never use the words attached, enclosed, beigelegt, beiliegend, partial, final, sufficient or hearsay; never write a catalogue document id (such as A1, B3, C2); never say whether a record will be adequate; do not contradict other paragraphs of the same episode; keep parties, dates and amounts mutually consistent. Vary sentence openings and register; avoid formulaic templates.

Return exactly one JSON object mapping every paragraph id in brief.json to its text, and nothing else."""

BANNED = ("attached", "enclosed", "beigelegt", "beiliegend", "hearsay")


def _problems(brief: dict, texts: dict) -> list[str]:
    ids = [p["id"] for p in brief["paragraphs"]]
    out: list[str] = []
    missing = [i for i in ids if i not in texts]
    extra = [i for i in texts if i not in ids]
    if missing:
        out.append("missing paragraph ids: " + ", ".join(missing))
    if extra:
        out.append("unknown paragraph ids: " + ", ".join(extra))
    doc_ids = [d["document_id"] for d in brief.get("catalog", [])]
    for pid in ids:
        value = texts.get(pid)
        if not isinstance(value, str) or len(value.strip()) < 40:
            out.append(f"{pid}: text missing or shorter than 40 characters")
            continue
        low = value.lower()
        for word in BANNED:
            if re.search(r"\b" + word, low):
                out.append(f"{pid}: banned word {word!r}")
        for doc in doc_ids:
            if re.search(r"\b" + re.escape(doc) + r"\b", value):
                out.append(f"{pid}: catalogue document id {doc} appears in the prose")
    return out


def write_one(ep_dir: Path, model: str, max_attempts: int = 3) -> dict:
    brief = json.loads((ep_dir / "brief.json").read_text())
    messages = [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": json.dumps(brief, ensure_ascii=False)}]
    receipts: list[dict] = []
    for attempt in range(max_attempts):
        r = transport.call_with_transport_retry(messages, model=model, max_tokens=8000, temperature=0.4 if attempt else 0.2, provider_only=None)
        receipts.append({"attempt": attempt, "ok": r["ok"], "cost_usd": r.get("cost_usd"), "finish_reason": r.get("finish_reason"),
                         "error": (r.get("error") or "")[:200] or None})
        if not r["ok"]:
            continue
        raw = r["content"].strip()
        if raw.startswith("```"):
            raw = raw.strip("`").split("\n", 1)[1].rsplit("```", 1)[0]
        try:
            texts = json.loads(raw)
        except Exception:
            receipts[-1]["problems"] = ["unparsable JSON"]
            messages = messages[:2] + [{"role": "user", "content": "Your previous reply was not valid JSON. Return one JSON object only."}]
            continue
        problems = _problems(brief, texts)
        receipts[-1]["problems"] = problems
        if not problems:
            ordered = {p["id"]: str(texts[p["id"]]).strip() for p in brief["paragraphs"]}
            (ep_dir / "texts.json").write_text(json.dumps(ordered, ensure_ascii=False, indent=1) + "\n")
            return {"episode": ep_dir.name, "ok": True, "attempts": receipts,
                    "cost_usd": round(sum(x.get("cost_usd") or 0 for x in receipts), 6)}
        messages = messages[:2] + [{"role": "user", "content": "Your previous reply broke these rules; rewrite the whole object correctly.\n" + "\n".join(problems)}]
    return {"episode": ep_dir.name, "ok": False, "attempts": receipts,
            "cost_usd": round(sum(x.get("cost_usd") or 0 for x in receipts), 6)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--model", default="anthropic/claude-sonnet-5")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--only-missing", action="store_true")
    a = ap.parse_args()
    data = Path(a.data)
    dirs = sorted(p for p in (data / "gen").iterdir() if (p / "brief.json").exists())
    if a.only_missing:
        dirs = [p for p in dirs if not (p / "texts.json").exists()]
    with concurrent.futures.ThreadPoolExecutor(max_workers=a.workers) as pool:
        results = list(pool.map(lambda d: write_one(d, a.model), dirs))
    summary = {"contract": "casepath.arena-v1-write-receipts/1.0.0", "writer_model": a.model, "episodes": len(results),
               "written": sum(r["ok"] for r in results), "failed": sum(not r["ok"] for r in results),
               "cost_usd": round(sum(r["cost_usd"] for r in results), 4), "results": results}
    (data / "WRITE_RECEIPTS.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False))
    print(json.dumps({k: summary[k] for k in ("writer_model", "episodes", "written", "failed", "cost_usd")}))
    for r in results:
        if not r["ok"]:
            print("FAILED", r["episode"], json.dumps(r["attempts"][-1].get("problems", [])[:4], ensure_ascii=False))


if __name__ == "__main__":
    main()
