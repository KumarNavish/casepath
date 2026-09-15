"""Product study on the real 150-claim intake corpus.

For each selected claim the product's own pipeline renders the actually received sources (the customer
message plus any attached PDFs/JPEGs), assembles the real source prefix with its public pointer aliases,
and the real SYSTEM_PROMPT/OUTPUT_SCHEMA are sent to the model. The returned proposal is then decoded
twice with the product decoder: gate off (the shipped behaviour) and gate on (CTES). The difference is
measured as needs whose proposed state `received` rests only on customer-message pointers.
"""
from __future__ import annotations

import argparse, concurrent.futures, json
from pathlib import Path

from casepath_api import evidential_channel_gate_v1 as gate
from casepath_api.arena_v1 import transport
from casepath_api.native_inference_v1 import SourcePrefixAssembler
from casepath_api.native_live_workspace_v1 import (
    OUTPUT_SCHEMA, SYSTEM_PROMPT, decode_provisional_proposal, render_claim_sources,
)
from casepath_api.workspace_corpus import PublicCorpus, default_workspace_corpus_root

OBSERVED_AT = "2026-09-15T09:00:00+02:00"


def prepare(corpus, claim_id: str, assets: Path):
    sources = render_claim_sources(corpus, claim_id, observed_at=OBSERVED_AT)
    return sources, SourcePrefixAssembler(assets).assemble(
        sources=sources, observed_at=OBSERVED_AT, prior_self=(), system_prompt=SYSTEM_PROMPT)


def run_claim(corpus, claim_id: str, assets: Path, model: str, max_tokens: int) -> dict:
    sources, prepared = prepare(corpus, claim_id, assets)
    roles = {s.artifact_id: s.admission_receipt.get("artifact_role") for s in sources}
    user = prepared.messages[1]["content"]
    text = "\n".join(part["text"] for part in user if part.get("type") == "text") if isinstance(user, list) else str(user)
    images = sum(1 for part in (user if isinstance(user, list) else []) if part.get("type") != "text")
    messages = [{"role": "system", "content": SYSTEM_PROMPT + "\n\nReturn JSON matching this schema:\n" + json.dumps(OUTPUT_SCHEMA)},
                {"role": "user", "content": text}]
    r = transport.call_with_transport_retry(messages, model=model, max_tokens=max_tokens, temperature=0.0, provider_only=["anthropic"])
    if not r["ok"]:
        return {"claim_id": claim_id, "status": "transport_failure", "error": str(r.get("error"))[:200]}
    content = r["content"].strip()
    if content.startswith("```"):
        content = content.strip("`").split("\n", 1)[1].rsplit("```", 1)[0]
    try:
        actor_output = json.loads(content)
        off = decode_provisional_proposal(actor_output=actor_output, prepared=prepared, channel_gate=False)
        on = decode_provisional_proposal(actor_output=actor_output, prepared=prepared, channel_gate=True)
    except Exception as exc:
        return {"claim_id": claim_id, "status": "decode_failure", "error": f"{type(exc).__name__}: {exc}"[:300], "cost_usd": r.get("cost_usd")}
    capped = [d for d in on["evidential_channel_gate"]["decisions"] if d["capped"]]
    return {"claim_id": claim_id, "status": "ok", "artifact_roles": roles, "has_attachment": "attachment" in roles.values(),
            "images_in_prefix": images, "needs": len(off["needs"]),
            "states_off": {n["need_id"]: n["state"] for n in off["needs"]},
            "states_on": {n["need_id"]: n["state"] for n in on["needs"]},
            "received_off": sum(n["state"] == "received" for n in off["needs"]),
            "received_on": sum(n["state"] == "received" for n in on["needs"]),
            "capped": capped, "proposal_sha256_off": off["proposal_sha256"], "proposal_sha256_on": on["proposal_sha256"],
            "cost_usd": r.get("cost_usd"), "usage": r.get("usage")}


def main() -> None:
    ap = argparse.ArgumentParser(); ap.add_argument("--claims", nargs="*", default=[]); ap.add_argument("--with-attachment", type=int, default=6)
    ap.add_argument("--message-only", type=int, default=6); ap.add_argument("--model", default="anthropic/claude-opus-5")
    ap.add_argument("--max-tokens", type=int, default=6000); ap.add_argument("--assets", required=True); ap.add_argument("--out", required=True); ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()
    root = default_workspace_corpus_root()
    corpus = PublicCorpus(root)
    manifest = corpus.identity
    rows = json.loads((root / "manifest.json").read_text())["claims"]
    with_att = [c["claim_id"] for c in rows if any(x.get("role") == "attachment" for x in c["observable_artifacts"])]
    msg_only = [c["claim_id"] for c in rows if not any(x.get("role") == "attachment" for x in c["observable_artifacts"])]
    claims = a.claims or (with_att[: a.with_attachment] + msg_only[: a.message_only])
    assets = Path(a.assets); assets.mkdir(parents=True, exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=a.workers) as pool:
        results = list(pool.map(lambda c: run_claim(corpus, c, assets, a.model, a.max_tokens), claims))
    ok = [r for r in results if r["status"] == "ok"]
    summary = {"contract": "casepath.ctes-product-corpus-study/1.0.0", "corpus_identity": manifest, "model": a.model,
               "claims": len(results), "ok": len(ok), "failures": [r for r in results if r["status"] != "ok"],
               "claims_with_attachment": sum(r.get("has_attachment") for r in ok),
               "needs_total": sum(r["needs"] for r in ok),
               "received_off_total": sum(r["received_off"] for r in ok), "received_on_total": sum(r["received_on"] for r in ok),
               "capped_needs_total": sum(len(r["capped"]) for r in ok),
               "claims_with_capped_need": sum(bool(r["capped"]) for r in ok),
               "cost_usd": round(sum((r.get("cost_usd") or 0) for r in results), 4), "results": results}
    Path(a.out).write_text(json.dumps(summary, indent=1, ensure_ascii=False))
    print(json.dumps({k: summary[k] for k in ("claims", "ok", "claims_with_attachment", "needs_total", "received_off_total", "received_on_total", "capped_needs_total", "claims_with_capped_need", "cost_usd")}, indent=1))
    for r in ok:
        if r["capped"]:
            print(" ", r["claim_id"], "attachment" if r["has_attachment"] else "message-only", [(c["need_id"], c["proposed_state"], "->", c["gated_state"], c["support_channels"]) for c in r["capped"]][:3])


if __name__ == "__main__":
    main()
