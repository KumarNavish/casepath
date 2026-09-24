"""Public command-line API for CasePath-Bench-v3 submissions and dev scoring."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from statistics import fmean
from typing import Any, Literal

from baselines.public_alias_rule_v3 import alias_rule_baseline_v3
from contracts.custom_factorial_v3 import PublicBenchmarkManifestV3
from contracts.schema import AcceptanceContract, CandidateArtifact
from manifests.digests import canonical_json_bytes, digest_json
from scorers.aggregate import EVALUATOR_VERSION, evaluate_candidate
from scorers.identity import scorer_code_sha256

ROOT = Path(__file__).resolve().parents[1]
MAX_SUBMISSION_BYTES = 64 * 1024 * 1024
MAX_ROW_BYTES = 1024 * 1024
MAX_COMPONENTS = {
    "concepts": 512,
    "relations": 2048,
    "branch_predicates": 256,
    "documents": 512,
    "terminal_outcome_ids": 64,
    "abstained_concept_ids": 512,
}
Split = Literal["public_dev", "hidden_test", "all"]

HIGHER_IS_BETTER_METRICS = frozenset(
    {
        "required_node_recall",
        "required_node_precision",
        "required_node_f1",
        "required_edge_recall",
        "required_edge_precision",
        "required_edge_f1",
        "partial_order_accuracy",
        "branch_predicate_accuracy",
        "valid_path_rate",
        "terminal_outcome_coverage",
        "critical_evidence_recall",
        "valid_chain_precision",
        "fact_chain_completeness",
        "evidence_obligation_completeness",
        "document_state_accuracy",
        "exact_source_support_rate",
        "exact_source_span_rate",
        "provenance_chain_inheritance_rate",
        "traceability_exactness",
    }
)
LOWER_IS_BETTER_UNIT_METRICS = frozenset(
    {
        "forbidden_concept_violation_rate",
        "forbidden_relation_violation_rate",
        "unnecessary_document_rate",
        "evidence_gap_rate",
        "orphan_document_rate",
        "wrong_branch_attachment_rate",
        "premature_request_rate",
        "duplicate_request_rate",
        "unsupported_claim_rate",
        "stale_source_usage_rate",
        "brier_score",
        "expected_calibration_error",
    }
)


class PublicLeaderboardError(ValueError):
    """Public submission bytes are malformed, incomplete, or out of scope."""


def _strict_json(raw: str, line_number: int) -> Any:
    def reject_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise PublicLeaderboardError(
                    f"line {line_number} contains duplicate JSON key {key!r}"
                )
            result[key] = value
        return result

    def reject_constant(value: str) -> None:
        raise PublicLeaderboardError(f"line {line_number} contains non-finite JSON value {value!r}")

    try:
        return json.loads(
            raw,
            object_pairs_hook=reject_pairs,
            parse_constant=reject_constant,
        )
    except json.JSONDecodeError as exc:
        raise PublicLeaderboardError(f"line {line_number} is not strict JSON: {exc.msg}") from exc


def _validate_component_bounds(value: dict[str, Any], line_number: int) -> None:
    candidate = value.get("candidate")
    if not isinstance(candidate, dict):
        return
    for field, maximum in MAX_COMPONENTS.items():
        items = candidate.get(field)
        if isinstance(items, list) and len(items) > maximum:
            raise PublicLeaderboardError(
                f"line {line_number} has {len(items)} {field}; maximum is {maximum}"
            )


def _load_manifest(root: Path) -> PublicBenchmarkManifestV3:
    return PublicBenchmarkManifestV3.model_validate_json((root / "manifest.json").read_bytes())


def _expected_case_ids(manifest: PublicBenchmarkManifestV3, split: Split) -> tuple[str, ...]:
    return tuple(item.case_id for item in manifest.cases if split == "all" or item.split == split)


def load_submission(
    *, path: Path, manifest: PublicBenchmarkManifestV3, split: Split
) -> dict[str, CandidateArtifact]:
    if path.stat().st_size > MAX_SUBMISSION_BYTES:
        raise PublicLeaderboardError(f"submission exceeds {MAX_SUBMISSION_BYTES} bytes")
    expected = set(_expected_case_ids(manifest, split))
    candidates: dict[str, CandidateArtifact] = {}
    try:
        raw_lines = path.read_bytes().splitlines()
        decoded_lines = [line.decode("utf-8") for line in raw_lines]
    except UnicodeDecodeError as exc:
        raise PublicLeaderboardError("submission is not valid UTF-8") from exc
    if len(decoded_lines) > len(expected):
        raise PublicLeaderboardError("submission contains more rows than the requested split")
    for line_number, raw_line in enumerate(decoded_lines, 1):
        if len(raw_line.encode("utf-8")) > MAX_ROW_BYTES:
            raise PublicLeaderboardError(f"line {line_number} exceeds {MAX_ROW_BYTES} bytes")
        if raw_line.strip():
            value = _strict_json(raw_line, line_number)
            if not isinstance(value, dict) or set(value) != {"case_id", "candidate"}:
                raise PublicLeaderboardError(
                    f"line {line_number} must contain only case_id and candidate"
                )
            _validate_component_bounds(value, line_number)
            case_id = value["case_id"]
            candidate = CandidateArtifact.model_validate(value["candidate"])
            if not isinstance(case_id, str) or candidate.case_id != case_id:
                raise PublicLeaderboardError(f"line {line_number} has inconsistent case IDs")
            if case_id in candidates:
                raise PublicLeaderboardError(f"duplicate prediction for {case_id}")
            candidates[case_id] = candidate
    supplied = set(candidates)
    if supplied != expected:
        missing = sorted(expected - supplied)
        extra = sorted(supplied - expected)
        raise PublicLeaderboardError(
            f"submission roster differs: missing={missing[:5]} extra={extra[:5]}"
        )
    return candidates


def write_alias_rule_baseline(*, root: Path, output: Path) -> str:
    manifest = _load_manifest(root)
    rules = json.loads((root / "rules/static-rule-templates-v3.json").read_text())
    rows: list[bytes] = []
    for case in manifest.cases:
        if case.split != "public_dev":
            continue
        claim = json.loads((root / case.observable_claim_path).read_text())
        registry = json.loads((root / case.source_registry_path).read_text())
        candidate = alias_rule_baseline_v3(claim=claim, rules=rules, registry=registry)
        rows.append(
            canonical_json_bytes(
                {"case_id": case.case_id, "candidate": candidate.model_dump(mode="json")}
            )
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(b"\n".join(rows) + b"\n")
    return hashlib.sha256(output.read_bytes()).hexdigest()


def _worst_case_metrics(contract: AcceptanceContract, metric_names: set[str]) -> dict[str, float]:
    """Return the preregistered ITT score for an unscorable case."""

    unknown = metric_names.difference(
        HIGHER_IS_BETTER_METRICS,
        LOWER_IS_BETTER_UNIT_METRICS,
        {"critical_step_omission", "incompatible_requirement_count"},
    )
    if unknown:
        raise PublicLeaderboardError(f"failure policy lacks metric directions: {sorted(unknown)}")
    values = {
        metric: (0.0 if metric in HIGHER_IS_BETTER_METRICS else 1.0) for metric in metric_names
    }
    if "critical_step_omission" in values:
        values["critical_step_omission"] = float(
            sum(
                concept.criticality
                for concept in contract.concepts
                if concept.requirement.value == "mandatory"
            )
        )
    if "incompatible_requirement_count" in values:
        obligation_count = len(contract.evidence_contracts)
        values["incompatible_requirement_count"] = float(
            obligation_count * (obligation_count - 1) // 2
        )
    return values


def score_dev(*, root: Path, submission: Path) -> dict[str, Any]:
    manifest = _load_manifest(root)
    candidates = load_submission(path=submission, manifest=manifest, split="public_dev")
    case_by_id = {item.case_id: item for item in manifest.cases}
    metric_values: dict[str, list[float]] = defaultdict(list)
    domain_values: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    accepted = 0
    evaluation_failure_count = 0
    for case_id, candidate in candidates.items():
        case = case_by_id[case_id]
        assert case.public_gold_path is not None
        gold = json.loads((root / case.public_gold_path).read_text())
        contract = AcceptanceContract.model_validate(gold["acceptance_contract"])
        receipt = evaluate_candidate(contract, candidate)
        accepted += receipt.accepted
        evaluation_failure_count += bool(receipt.evaluation_failures)
        values = (
            _worst_case_metrics(contract, set(receipt.metrics))
            if receipt.evaluation_failures
            else receipt.metrics
        )
        for metric, value in values.items():
            metric_values[metric].append(value)
            domain_values[case.domain][metric].append(value)
    payload: dict[str, Any] = {
        "contract": "casepath.public-dev-score/3.0.0",
        "benchmark_manifest_sha256": manifest.manifest_sha256,
        "submission_sha256": hashlib.sha256(submission.read_bytes()).hexdigest(),
        "evaluator_version": EVALUATOR_VERSION,
        "scorer_code_sha256": scorer_code_sha256(ROOT),
        "case_count": len(candidates),
        "accepted_case_count": accepted,
        "evaluation_failure_case_count": evaluation_failure_count,
        "metrics": {
            metric: {"mean": fmean(values), "denominator": len(values)}
            for metric, values in sorted(metric_values.items())
        },
        "metrics_by_domain": {
            domain: {
                metric: {"mean": fmean(values), "denominator": len(values)}
                for metric, values in sorted(metrics.items())
            }
            for domain, metrics in sorted(domain_values.items())
        },
    }
    payload["receipt_sha256"] = digest_json(payload)
    return payload


def verify_hidden_protocol(root: Path) -> dict[str, Any]:
    manifest = _load_manifest(root)
    hidden = [item for item in manifest.cases if item.split == "hidden_test"]
    if len(hidden) != 90 or any(
        item.public_gold_path is not None or item.hidden_contract_commitment_sha256 is None
        for item in hidden
    ):
        raise PublicLeaderboardError("hidden-test visibility contract is broken")
    payload: dict[str, Any] = {
        "contract": "casepath.hidden-evaluator-interface-check/3.0.0",
        "manifest_sha256": manifest.manifest_sha256,
        "evaluator_api_contract": manifest.evaluator_api_contract,
        "hidden_case_count": len(hidden),
        "hidden_commitment_bundle_sha256": manifest.hidden_test_contract_bundle_sha256,
        "test_gold_files_exposed": False,
        "submission_format": "jsonl_one_case_id_and_candidate_object_per_line",
        "failure_policy": "invalid_missing_or_system_failure_receives_frozen_worst_score",
    }
    payload["receipt_sha256"] = digest_json(payload)
    return payload


def _write_json(path: Path | None, payload: dict[str, Any]) -> None:
    raw = canonical_json_bytes(payload)
    if path is None:
        print(raw.decode())
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate-submission")
    validate.add_argument("--submission", type=Path, required=True)
    validate.add_argument("--split", choices=("public_dev", "hidden_test", "all"), required=True)
    baseline = commands.add_parser("baseline-dev")
    baseline.add_argument("--output", type=Path, required=True)
    score = commands.add_parser("score-dev")
    score.add_argument("--submission", type=Path, required=True)
    score.add_argument("--output", type=Path)
    hidden = commands.add_parser("verify-hidden-interface")
    hidden.add_argument("--output", type=Path)
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        manifest = _load_manifest(args.root)
        if args.command == "validate-submission":
            candidates = load_submission(
                path=args.submission,
                manifest=manifest,
                split=args.split,
            )
            print(json.dumps({"valid": True, "case_count": len(candidates)}))
        elif args.command == "baseline-dev":
            digest = write_alias_rule_baseline(root=args.root, output=args.output)
            print(json.dumps({"written": str(args.output), "sha256": digest}))
        elif args.command == "score-dev":
            _write_json(args.output, score_dev(root=args.root, submission=args.submission))
        else:
            _write_json(args.output, verify_hidden_protocol(args.root))
    except (OSError, ValueError) as exc:
        print(json.dumps({"valid": False, "error": str(exc)}))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
