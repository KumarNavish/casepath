"""Executable independent verification of the public CasePath-Bench dev release."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from dataclasses import asdict
from pathlib import Path
from typing import Any

from contracts.custom_factorial_v3 import PublicBenchmarkManifestV3
from contracts.model_projection import ModelVisibleSourceRegistryV3
from contracts.schema import AcceptanceContract
from manifests.digests import canonical_json_bytes, digest_json
from scorers.aggregate import evaluate_candidate
from validation.independent_evaluator_v3 import (
    REPORTED_ENDPOINTS_V3,
    audit_contracts_independently_v3,
    build_reference_candidate_v3,
    evaluate_independently_v3,
)


class IndependentReleaseVerificationError(ValueError):
    """The public release cannot reproduce its independent dev audit."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_independent_release_v3(root: Path) -> dict[str, Any]:
    release_root = root.resolve()
    manifest = PublicBenchmarkManifestV3.model_validate_json(
        (release_root / "manifest.json").read_bytes()
    )
    file_rows = {item.relative_path: item for item in manifest.files}
    for relative, row in file_rows.items():
        path = release_root / relative
        if not path.is_file() or path.is_symlink() or _sha256(path) != row.file_sha256:
            raise IndependentReleaseVerificationError(f"release file differs: {relative}")

    contracts: list[AcceptanceContract] = []
    value_match_count = 0
    acceptance_match_count = 0
    dev_cases = [item for item in manifest.cases if item.split == "public_dev"]
    if len(dev_cases) != 60:
        raise IndependentReleaseVerificationError("public dev roster must contain 60 cases")
    for case in dev_cases:
        if case.public_gold_path is None:
            raise IndependentReleaseVerificationError(f"dev gold is missing: {case.case_id}")
        registry = ModelVisibleSourceRegistryV3.model_validate_json(
            (release_root / case.source_registry_path).read_bytes()
        )
        if registry.case_id != case.case_id:
            raise IndependentReleaseVerificationError(
                f"source registry has the wrong case ID: {case.case_id}"
            )
        gold_payload = json.loads((release_root / case.public_gold_path).read_bytes())
        contract = AcceptanceContract.model_validate(gold_payload["acceptance_contract"])
        if contract.case_id != case.case_id:
            raise IndependentReleaseVerificationError(
                f"dev contract has the wrong case ID: {case.case_id}"
            )
        contracts.append(contract)
        candidate = build_reference_candidate_v3(contract)
        independent = evaluate_independently_v3(contract, candidate)
        production = evaluate_candidate(contract, candidate)
        for endpoint in REPORTED_ENDPOINTS_V3:
            if independent.metrics[endpoint] != production.metrics[endpoint]:
                raise IndependentReleaseVerificationError(
                    f"independent/production endpoint mismatch: {case.case_id}/{endpoint}"
                )
            value_match_count += 1
        if independent.accepted != production.accepted or not independent.accepted:
            raise IndependentReleaseVerificationError(
                f"independent/production acceptance mismatch: {case.case_id}"
            )
        acceptance_match_count += 1

    audit = audit_contracts_independently_v3(contracts, expected_case_count=60)
    if not audit.eligible:
        raise IndependentReleaseVerificationError(f"independent dev audit failed: {audit.failures}")
    payload: dict[str, Any] = {
        "contract": "casepath.independent-release-verification/3.0.0",
        "manifest_sha256": manifest.manifest_sha256,
        "verified_manifest_file_count": len(file_rows),
        "verified_source_registry_count": 60,
        "dev_contract_count": 60,
        "reported_endpoint_count": 11,
        "independent_production_endpoint_value_match_count": value_match_count,
        "independent_production_acceptance_match_count": acceptance_match_count,
        "independent_audit": asdict(audit),
        "eligible": True,
        "runtime_model_calls": 0,
    }
    payload["receipt_sha256"] = digest_json(payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(os.environ.get("CASEPATH_BENCHMARK_ROOT", ".")),
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    receipt = verify_independent_release_v3(args.root)
    raw = canonical_json_bytes(receipt) + b"\n"
    if args.output is None:
        print(raw.decode(), end="")
    else:
        args.output.write_bytes(raw)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
