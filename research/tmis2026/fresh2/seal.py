"""Seal fresh2: statistics from the model-free checks, the blind-check summary and MANIFEST.json with the SHA-256 of
every file. No model calls. Run after theft/build_theft.py, tenancy/build.py assemble and tenancy/blind_compare.py.
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
run = subprocess.run([sys.executable, str(HERE / "check.py")], capture_output=True, text=True)
checks = json.loads(run.stdout)
assert set(checks["failures"]) <= {"manifest_hashes_match"}, checks["failures"]
blind = json.loads((HERE / "tenancy" / "build" / "blind_check" / "comparison.json").read_text())["summary"]
first = json.loads((HERE / "tenancy" / "build" / "blind_check" / "comparison_first_reading.json").read_text())
keep = ("claims_read", "fact_judgements", "content_item_judgements", "facts_strict_agreement", "facts_accepted",
        "content_items_agreement", "claims_all_strict", "claims_all_accepted", "state_x_reading",
        "stated_facts_strict_by_expression", "disagreements", "content_item_disagreements")
stats = {k: v["detail"] for k, v in checks["checks"].items() if k != "manifest_hashes_match" and "detail" in v}
stats["blind_check"] = {"first_reading": {k: first[k] for k in keep}, "final": {k: blind[k] for k in keep},
                        "corrected_after_reading": ["f2cl_7850a89c062dfd72"]}
files = sorted(p for p in HERE.rglob("*") if p.is_file() and "__pycache__" not in p.parts and p.name != "MANIFEST.json")
manifest = {
    "contract": "casepath.fresh2-study3-data/1.0.0",
    "sealed": "2026-11-10",
    "rule": "No design, baseline or scorer runs on these data before research/tmis2026/ANALYSIS_PLAN_STUDY3.md is committed (guard.py).",
    "note": "Built and sealed before any compared design ran on these data. No design output was consulted. No evaluated model read or wrote the data.",
    "author_model": "Claude Opus 5.5 (agent session; not an evaluated model)",
    "blind_reader_model": "claude-fable-5-2 (separate sessions, prompt only; not an evaluated model)",
    "evaluated_models_excluded": ["openai/gpt-6-luna", "openai/gpt-6.1-terra"],
    "checks_passed": sorted(k for k, v in checks["checks"].items() if v["ok"]),
    "statistics": stats,
    "files": {str(p.relative_to(HERE)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
}
(HERE / "MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + "\n")
print(json.dumps({"files": len(manifest["files"]), "checks_passed": manifest["checks_passed"]}, indent=1))
