"""Seal the fresh datasets: statistics, oracle check and MANIFEST.json with SHA-256 hashes.

No model calls. Run after theft/build_theft.py and tenancy/generate.py.
"""
import hashlib
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import tenancy_fresh as tf  # noqa: E402
import theft_fresh as th  # noqa: E402

oracle = subprocess.run([sys.executable, str(HERE / "tenancy" / "oracle_check.py")], capture_output=True, text=True)
assert oracle.returncode == 0, oracle.stdout + oracle.stderr
log = json.loads((HERE / "tenancy" / "build" / "generation_log.json").read_text())

ids = tf.claim_ids("test")
refs = [tf.reference(c) for c in ids]
intakes = [tf.intake(c) for c in ids]
atts = [a for r in refs for a in r["attachments"]]
routing_claims = [r for r in refs if r["implicit_flags"]]
words = [len(i["customer_message"]["body"].split()) for i in intakes]

# blind-check agreement over every checked draft, and on the accepted drafts
drafts = [a for s in log["slots"] for c in s["claims"] for a in c["attempts"] if "facts" in a]
first = [c["attempts"][0] for s in log["slots"] for c in s["claims"] if c["attempts"] and "facts" in c["attempts"][0]]
fact_rows = [x for a in drafts for x in a["facts"].values()]
field_rows = [x for a in drafts for x in a["fields"]]
by_state = Counter()
by_state_ok = Counter()
for a in drafts:
    for f, x in a["facts"].items():
        by_state[x["expected"]] += 1
        by_state_ok[x["expected"]] += x["expected"] == x["got"]
claims_logged = [c for s in log["slots"] for c in s["claims"]]
stats = {
    "tenancy": {
        "claims": len(ids), "families": len({r["family_id"] for r in refs}),
        "by_dispute_family": dict(Counter(r["family"] for r in refs)),
        "combinations": sorted({(r["family"], tuple(sorted(k for k, v in r["scenario"].items() if v))) for r in refs}),
        "max_active_branch_flags": max(sum(r["scenario"].values()) for r in refs),
        "claims_with_2plus_active_flags": sum(sum(r["scenario"].values()) >= 2 for r in refs),
        "language": dict(Counter(i["submission"]["language"] for i in intakes)),
        "channel": dict(Counter(i["submission"]["channel"] for i in intakes)),
        "words_min_max": [min(words), max(words)],
        "claims_with_open_fact": sum(r["open_fact"] is not None for r in refs),
        "open_fact_true_value": dict(Counter(str(r["open_fact"]["true_value"]) for r in refs if r["open_fact"])),
        "routing_fact_claims": len(routing_claims),
        "routing_fact_unmentioned": sum(r["fact_states"][next(iter(r["implicit_flags"]))] == "unmentioned"
                                        for r in routing_claims),
        "claims_with_attachments": sum(bool(r["attachments"]) for r in refs),
        "attachments": len(atts), "attachments_sufficient": sum(a["sufficient"] for a in atts),
        "attachments_by_type": dict(Counter(a["document_type"] for a in atts)),
        "document_states": dict(Counter(s for r in refs for s in r["document_states"].values())),
        "required_documents": sum(len(r["request_set"]) for r in refs),
        "held_documents": sum(len(r["held_set"]) for r in refs),
        "oracle": json.loads(oracle.stdout),
        "generation": {
            "model": log["model"], "seed": log["seed"], "spend_usd": log["fresh_generation_spend_usd"],
            "slots": len(log["slots"]), "claims_written": len(claims_logged),
            "claims_replaced": sum(1 for s in log["slots"] for c in s["claims"] if not c["accepted"]),
            "slots_unfilled": sum(1 for s in log["slots"] if not any(c["accepted"] for c in s["claims"])),
            "accepted_claims_by_drafts": dict(Counter(len(c["attempts"]) for c in claims_logged if c["accepted"])),
            "drafts_checked": len(drafts),
            "blind_check_fact_agreement_all_drafts": sum(x["expected"] == x["got"] for x in fact_rows) / len(fact_rows),
            "blind_check_field_agreement_all_drafts": (sum(x["expected"] == x["got"] for x in field_rows) / len(field_rows)) if field_rows else None,
            "blind_check_fact_agreement_first_drafts": sum(x["expected"] == x["got"] for a in first for x in a["facts"].values())
                                                      / sum(len(a["facts"]) for a in first),
            "blind_check_field_agreement_first_drafts": (sum(x["expected"] == x["got"] for a in first for x in a["fields"])
                                                        / max(1, sum(len(a["fields"]) for a in first))),
            "first_drafts_fully_agreeing": sum(a["facts_agree"] and a["fields_agree"] and a["length_ok"] for a in first) / len(first),
            "fact_agreement_by_expected_state_all_drafts": {k: by_state_ok[k] / by_state[k] for k in by_state},
        },
    },
    "theft": {
        "stories": sorted({p["story"] for p in th.pairs()}),
        "pairs": dict(Counter(p["kind"] for p in th.pairs())), "texts": len(th.texts()),
        "build_checks": th.benchmark()["fresh_build"]["checks"],
    },
}
stats["tenancy"]["combinations"] = [[f, list(c)] for f, c in stats["tenancy"]["combinations"]]

files = sorted(p for p in HERE.rglob("*") if p.is_file() and "__pycache__" not in p.parts and p.name != "MANIFEST.json")
manifest = {
    "contract": "casepath.fresh-study2-data/1.0.0",
    "sealed": "2026-11-09",
    "note": "Built and sealed before any compared design ran on these data. No method output was consulted.",
    "generator_model": log["model"],
    "statistics": stats,
    "files": {str(p.relative_to(HERE)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
}
(HERE / "MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + "\n")
print(json.dumps(stats, ensure_ascii=False, indent=1))
