"""Summarise cache-only replays: each product version against the stored runs, and the speed branch against the tested
commit (whole stored result, field by field, by SHA-256 of its canonical JSON).

    python3 harness/speed/replay_compare.py --base base6a7 --branch branch64ff   -> runs/speed/replay_summary.{json,md}
"""
import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

TMIS = Path(__file__).resolve().parents[2]
OUT = TMIS / "runs" / "speed"
SCORED = ("plan", "plan_workflow_only")  # the scored checklists (theft: plan_ids too)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--branch", required=True)
    a = ap.parse_args()
    base = json.loads((OUT / f"replay_{a.base}.json").read_text())
    branch = json.loads((OUT / f"replay_{a.branch}.json").read_text())
    groups = defaultdict(Counter)
    diffs = []
    for key, b in branch.items():
        g = groups[(b["set"], b["file"])]
        g["case_runs"] += 1
        g["misses"] += b["misses"] > 0
        cmp_ = b["compare"] or {}
        scored = all(cmp_.get(f) for f in SCORED) and cmp_.get("plan_ids", True)
        g["scored_checklist_equal_stored"] += bool(scored)
        g["all_stored_fields_equal_stored"] += bool(cmp_) and all(v for k, v in cmp_.items() if k != "same_request_order")
        g["same_requests_as_stored"] += bool(cmp_.get("same_requests"))
        g["same_request_order_as_stored"] += bool(cmp_.get("same_request_order"))
        base_row = base.get(key)
        if base_row:
            bb, rb = base_row["replayed"], b["replayed"]
            g["base_scored_equal_stored"] += bool(base_row["compare"]) and all(base_row["compare"].get(f) for f in SCORED) and base_row["compare"].get("plan_ids", True)
            g["base_all_fields_equal_stored"] += bool(base_row["compare"]) and all(v for k, v in base_row["compare"].items() if k != "same_request_order")
            same_result = bb.get("result_sha256") == rb.get("result_sha256") and bb.get("routing_sha256") == rb.get("routing_sha256")
            g["whole_result_equal_to_tested_commit_replay"] += same_result
            g["same_requests_as_tested_commit_replay"] += sorted(base_row["replay_keys"]) == sorted(b["replay_keys"])
            if rb.get("checklist_equals_result") is not None:
                g["checklist_published"] += 1
                g["published_checklist_equals_result"] += all(rb["checklist_equals_result"].values())
            if not same_result:
                fields = sorted(f for f in set(bb.get("result_fields_sha256") or {}) | set(rb.get("result_fields_sha256") or {})
                                if (bb.get("result_fields_sha256") or {}).get(f) != (rb.get("result_fields_sha256") or {}).get(f))
                diffs.append({"key": key, "fields": fields, "base_status": bb.get("status"), "branch_status": rb.get("status")})
        if not scored or not cmp_ or not all(v for k, v in cmp_.items() if k != "same_request_order"):
            diffs.append({"key": key, "vs_stored": {k: v for k, v in cmp_.items() if not v}, "misses": b["misses"]})
    res = {"groups": {f"{s}:{f}": dict(c) for (s, f), c in sorted(groups.items())}, "differences": diffs}
    (OUT / "replay_summary.json").write_text(json.dumps(res, indent=1))
    cols = ["case_runs", "misses", "scored_checklist_equal_stored", "all_stored_fields_equal_stored", "base_scored_equal_stored",
            "base_all_fields_equal_stored", "whole_result_equal_to_tested_commit_replay", "same_requests_as_tested_commit_replay",
            "same_requests_as_stored", "same_request_order_as_stored", "checklist_published", "published_checklist_equals_result"]
    lines = ["| set:file | " + " | ".join(cols) + " |", "|---" * (len(cols) + 1) + "|"]
    for k, c in res["groups"].items():
        lines.append(f"| {k} | " + " | ".join(str(c.get(x, 0)) for x in cols) + " |")
    lines.append("\nDifferences:\n")
    lines += [json.dumps(d) for d in diffs]
    (OUT / "replay_summary.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
