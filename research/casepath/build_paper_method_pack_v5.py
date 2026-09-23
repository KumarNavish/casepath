from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
from pathlib import Path
from typing import Any

GOAL = "a9cd441ef939e36d7ed2c546b76aa41554813aba11ba1a379f23479ded4cc37b"
PACK_CONTRACT = "casepath.paper-method-pack/5.0.0"
HIDDEN_CONTRACT = "casepath.theft-confirmatory-analysis/5.0.0"
FORBIDDEN_TEXT = (
    "".join(("kumar", "0002")), "".join(("nav", "ish")),
    "".join(("university of ", "basel")), "".join(("uni", "bas")),
    "".join(("@uni", "bas.ch")), "sk-or-v1-", "/users/", "/home/", "openrouter_api_key",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n")


def record(path: Path) -> dict[str, Any]:
    return {"sha256": sha(path), "bytes": path.stat().st_size}


def scan_text(root: Path) -> list[dict[str, str]]:
    findings = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        try:
            text = path.read_text("utf-8").lower()
        except (UnicodeDecodeError, OSError):
            continue
        for token in FORBIDDEN_TEXT:
            if token in text:
                findings.append({"file": str(path.relative_to(root)), "token": token})
    return findings


def select_demo(benchmark: dict[str, Any]) -> dict[str, Any]:
    pair = next(
        row for row in benchmark["pairs"]
        if row["scenario"] == "PR_bicycle_claimed" and row["context_index"] == 0
    )
    units = {row["unit_id"]: row for row in benchmark["units"]}
    return {
        "customer_message": units[pair["true_unit_id"]]["customer_message"],
        "already_held": [],
        "demonstrates_pair_id": pair["pair_id"],
        "expected_signed_delta_options": pair["acceptable_signed_deltas"],
    }


def replace_current(pack_root: Path, version_dir: Path) -> None:
    current = pack_root / "current"
    temporary = pack_root / ".current.next"
    if temporary.exists() or temporary.is_symlink():
        if temporary.is_dir() and not temporary.is_symlink():
            shutil.rmtree(temporary)
        else:
            temporary.unlink()
    temporary.symlink_to(version_dir.name, target_is_directory=True)
    if current.exists() and current.is_dir() and not current.is_symlink():
        backup = pack_root / ".current.previous"
        if backup.exists():
            shutil.rmtree(backup)
        current.replace(backup)
        temporary.replace(current)
        shutil.rmtree(backup)
    else:
        os.replace(temporary, current)


def require_hidden(hidden: dict[str, Any]) -> None:
    if hidden.get("contract") != HIDDEN_CONTRACT:
        raise ValueError("hidden result contract mismatch")
    if hidden.get("mode") != "hidden":
        raise ValueError("paper pack requires the terminal hidden read")
    if hidden.get("claim_status") not in {"SUPPORTED", "UNSUPPORTED"}:
        raise ValueError("hidden result has no terminal claim status")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--propositions", type=Path, required=True)
    parser.add_argument("--source-snapshot", type=Path, required=True)
    parser.add_argument("--method-manifest", type=Path, required=True)
    parser.add_argument("--hidden-result", type=Path, required=True)
    parser.add_argument("--benchmark", type=Path, required=True)
    parser.add_argument("--pack-root", type=Path, required=True)
    args = parser.parse_args()

    hidden = json.loads(args.hidden_result.read_text())
    require_hidden(hidden)
    method = json.loads(args.method_manifest.read_text())
    if method.get("goal_contract_sha256") != GOAL:
        raise ValueError("method manifest goal mismatch")
    benchmark = json.loads(args.benchmark.read_text())
    if benchmark.get("contract") != "casepath.theft-causal-branch-benchmark/3.0.0":
        raise ValueError("benchmark v3 is required")

    inputs = {
        "PREPARED.json": args.prepared,
        "PROPOSITIONS.json": args.propositions,
        "SOURCE_SNAPSHOT.json": args.source_snapshot,
        "METHOD_MANIFEST.json": args.method_manifest,
        "HIDDEN_RESULT.json": args.hidden_result,
        "BENCHMARK.json": args.benchmark,
    }
    identity = {
        "inputs": {name: sha(path) for name, path in inputs.items()},
        "goal_contract_sha256": GOAL,
        "model": "openai/gpt-5.6-terra",
        "provider_only": ["openai"],
        "temperature": 0.0,
    }
    identity_hash = hashlib.sha256(
        json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    version = "theft-v5-" + identity_hash[:16]
    pack_root = args.pack_root.resolve()
    pack_root.mkdir(parents=True, exist_ok=True)
    version_dir = pack_root / version
    if version_dir.exists():
        shutil.rmtree(version_dir)
    version_dir.mkdir()
    for name, source in inputs.items():
        shutil.copy2(source, version_dir / name)
    dump(version_dir / "DEMO_CASE.json", select_demo(benchmark))

    runtime_files = (
        "PREPARED.json", "PROPOSITIONS.json", "SOURCE_SNAPSHOT.json",
        "DEMO_CASE.json", "METHOD_MANIFEST.json", "HIDDEN_RESULT.json", "BENCHMARK.json",
    )
    manifest = {
        "contract": PACK_CONTRACT,
        "scope": "authoritative Swiss household-theft claim evidence planning",
        "goal_contract_sha256": GOAL,
        "version": version,
        "method_freeze_sha256": sha(args.method_manifest),
        "hidden_result_sha256": sha(args.hidden_result),
        "benchmark_sha256": sha(args.benchmark),
        "files": {name: sha(version_dir / name) for name in runtime_files},
        "model": {
            "name": "openai/gpt-5.6-terra",
            "provider_only": ["openai"],
            "temperature": 0.0,
            "max_tokens": 10000,
        },
    }
    manifest_path = version_dir / "PACK_MANIFEST.json"
    dump(manifest_path, manifest)
    findings = scan_text(version_dir)
    if findings:
        raise ValueError({"anonymity_or_secret_findings": findings})
    replace_current(pack_root, version_dir)

    receipt = {
        "contract": "casepath.paper-method-pack-receipt/5.0.0",
        "goal_contract_sha256": GOAL,
        "version": version,
        "version_relative_path": version,
        "current_target": os.readlink(pack_root / "current"),
        "pack_manifest_sha256": sha(manifest_path),
        "files": {name: record(version_dir / name)
                  for name in (*runtime_files, "PACK_MANIFEST.json")},
        "anonymity_or_secret_findings": [],
        "hidden_gate_pass": bool(hidden.get("gate_pass")),
        "hidden_claim_status": hidden.get("claim_status"),
        "builder_sha256": sha(Path(__file__)),
        "efficacy_claim_not_required_for_product_install": True,
    }
    receipt_path = pack_root / "PACK_RECEIPT.json"
    dump(receipt_path, receipt)
    print(json.dumps(receipt, indent=2, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
