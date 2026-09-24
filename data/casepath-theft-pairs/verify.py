"""Check this release against the hashes recorded before the evaluation.

Uses only the Python standard library:

    python3 verify.py

It checks every file of the evaluated benchmark package against its manifest,
the reference contract against the hash bound in both benchmark amendments,
CasePath's frozen representation against the method-pack receipt, and the
corpus counts reported in the paper.
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BENCH = ROOT / "benchmark"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    errors = []

    manifest = load(BENCH / "MANIFEST.json")
    for row in manifest["files"]:
        path = BENCH / row["path"]
        if not path.is_file() or sha256(path) != row["sha256"]:
            errors.append("benchmark file differs from its manifest: " + row["path"])

    contract = sha256(ROOT / "reference-contract" / "theft.json")
    for name in ("BENCHMARK_AMENDMENT_V2.json", "BENCHMARK_AMENDMENT_V3.json"):
        if contract not in (BENCH / "benchmark" / name).read_text(encoding="utf-8"):
            errors.append("reference contract hash is not the one bound in " + name)

    receipt = load(ROOT / "representation" / "PACK_RECEIPT.json")["files"]
    for name in ("PREPARED.json", "PROPOSITIONS.json", "METHOD_MANIFEST.json"):
        if sha256(ROOT / "representation" / name) != receipt[name]["sha256"]:
            errors.append("representation file differs from the method-pack receipt: " + name)

    bench = load(BENCH / "benchmark" / "BENCHMARK_V3.json")
    snapshot = load(BENCH / "benchmark" / "SOURCE_SNAPSHOT_V2.json")
    passages = snapshot.get("passages", snapshot) if isinstance(snapshot, dict) else snapshot
    counts = {"cases": len(bench["units"]), "pairs": len(bench["pairs"]), "source_passages": len(passages)}
    for key, expected in {"cases": 72, "pairs": 36, "source_passages": 197}.items():
        if counts[key] != expected:
            errors.append(f"{key}: expected {expected}, found {counts[key]}")

    report = {
        "state": "failed" if errors else "verified",
        "benchmark_files_checked": len(manifest["files"]),
        **counts,
        "errors": errors,
    }
    print(json.dumps(report, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
