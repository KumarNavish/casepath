"""Check this release against the hashes recorded before the evaluation.

Uses only the Python standard library:

    python3 verify.py

It checks that every file of the evaluated benchmark package matches its
manifest, that each of the 90 held-out references matches the commitment
recorded in benchmark/cohort.json, and that each of the 24 held-out
state-change references matches the commitment in the state-change manifest.
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BENCH = ROOT / "benchmark"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    errors = []

    manifest = json.loads((BENCH / "manifest.json").read_text(encoding="utf-8"))
    for row in manifest["files"]:
        path = BENCH / row["relative_path"]
        if not path.is_file() or sha256(path) != row["file_sha256"]:
            errors.append("benchmark file differs from its manifest: " + row["relative_path"])

    cases = json.loads((BENCH / "cohort.json").read_text(encoding="utf-8"))["cases"]
    held_out = [c for c in cases if c["split"] == "hidden_test"]
    for case in held_out:
        path = ROOT / "heldout-references" / f"{case['case_id']}.json"
        if not path.is_file() or sha256(path) != case["hidden_contract_commitment_sha256"]:
            errors.append("held-out reference differs from its commitment: " + case["case_id"])

    stress = json.loads((BENCH / "state-stress" / "manifest.json").read_text(encoding="utf-8"))
    stress_held_out = [v for v in stress["variants"] if v["split"] == "hidden_test"]
    for variant in stress_held_out:
        path = ROOT / "heldout-state-stress-references" / f"{variant['stress_case_id']}.json"
        if not path.is_file() or sha256(path) != variant["hidden_expected_commitment_sha256"]:
            errors.append("held-out state-change reference differs: " + variant["stress_case_id"])

    report = {
        "state": "failed" if errors else "verified",
        "benchmark_files_checked": len(manifest["files"]),
        "claims": len(cases),
        "held_out_references_checked": len(held_out),
        "held_out_state_change_references_checked": len(stress_held_out),
        "errors": errors,
    }
    print(json.dumps(report, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
