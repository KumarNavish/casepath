"""Check this release against the hashes recorded before the evaluation.

Uses only the Python standard library:

    python3 verify.py
    python3 verify.py --restore-recipient STRING

It checks that every file of the evaluated benchmark package matches its
manifest, that each of the 90 held-out references matches the commitment
recorded in benchmark/cohort.json, and that each of the 24 held-out
state-change references matches the commitment in the state-change manifest.

The files listed in release-records/PSEUDONYMIZATION.json had one recipient
string replaced after the evaluation. They are checked against their released
hash, and the evaluated hash in that record must equal the manifest entry.
With --restore-recipient, the given string is checked against the recorded
commitment, put back in memory, and every restored file must then match its
manifest entry.
"""
import argparse
import base64
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BENCH = ROOT / "benchmark"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def restore(data: bytes, replacement: bytes, original: bytes) -> bytes:
    """Undo the substitution in a raw message, or in the embedded copy inside a claim JSON."""
    if data.count(replacement) == 1:
        return data.replace(replacement, original)
    raw_file = json.loads(data)["customer_message"]["raw_file"]
    raw = base64.b64decode(raw_file["content_base64"], validate=True)
    if raw.count(replacement) != 1 or len(raw) != raw_file["size_bytes"]:
        raise ValueError("embedded message does not carry the replacement once")
    restored = raw.replace(replacement, original)
    for old, new in (
        (raw_file["content_base64"].encode(), base64.b64encode(restored)),
        (raw_file["sha256"].encode(), sha256_bytes(restored).encode()),
    ):
        if data.count(old) != 1:
            raise ValueError("embedded field is not unique")
        data = data.replace(old, new)
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--restore-recipient", metavar="STRING")
    args = parser.parse_args()
    errors = []

    record = json.loads((ROOT / "release-records" / "PSEUDONYMIZATION.json").read_text(encoding="utf-8"))
    changed = {row["path"]: row for row in record["files"]}

    manifest = json.loads((BENCH / "manifest.json").read_text(encoding="utf-8"))
    for row in manifest["files"]:
        rel = "benchmark/" + row["relative_path"]
        path = ROOT / rel
        expected = row["file_sha256"]
        if rel in changed:
            if changed[rel]["evaluated_sha256"] != expected:
                errors.append("pseudonymization record differs from the manifest: " + rel)
            expected = changed[rel]["released_sha256"]
        if not path.is_file() or sha256(path) != expected:
            errors.append("benchmark file differs from its manifest: " + rel)
    manifest_paths = {"benchmark/" + row["relative_path"] for row in manifest["files"]}
    for rel in sorted(set(changed) - manifest_paths):
        errors.append("pseudonymized file is not in the manifest: " + rel)

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
        "pseudonymized_files_checked_against_released_hash": len(changed),
        "claims": len(cases),
        "held_out_references_checked": len(held_out),
        "held_out_state_change_references_checked": len(stress_held_out),
    }

    if args.restore_recipient is not None:
        original = args.restore_recipient.encode("utf-8")
        replacement = record["replacement"].encode("utf-8")
        restored = 0
        if sha256_bytes(original) != record["original_sha256"]:
            errors.append("the given string does not match the recorded commitment")
        elif len(original) != len(replacement):
            errors.append("the given string and the replacement differ in length")
        else:
            for rel, row in sorted(changed.items()):
                try:
                    data = restore((ROOT / rel).read_bytes(), replacement, original)
                except (ValueError, KeyError) as exc:
                    errors.append(f"cannot restore {rel}: {exc}")
                    continue
                if sha256_bytes(data) != row["evaluated_sha256"]:
                    errors.append("restored file differs from its evaluated hash: " + rel)
                else:
                    restored += 1
        report["restored_files_matching_evaluated_hash"] = restored
        report["state"] = "failed" if errors else "verified"

    report["errors"] = errors
    print(json.dumps(report, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
