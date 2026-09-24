"""Self-contained smoke tests shipped with CasePath-Bench-v3."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

from contracts.custom_factorial_v3 import PublicBenchmarkManifestV3
from contracts.schema import AcceptanceContract, Requirement
from contracts.state_stress_v3 import StateStressManifestV3
from manifests.digests import digest_json
from runners.public_leaderboard_v3 import (
    PublicLeaderboardError,
    load_submission,
    score_dev,
    verify_hidden_protocol,
    write_alias_rule_baseline,
)
from runners.state_stress_v3 import (
    build_state_stress_missing_floor_v3,
    score_state_stress_dev_v3,
)
from scorers.identity import scorer_code_sha256


def _release_root() -> Path:
    configured = os.environ.get("CASEPATH_BENCHMARK_ROOT")
    if configured is None:
        pytest.skip("CASEPATH_BENCHMARK_ROOT is required for packaged-release tests")
    return Path(configured).resolve()


def test_release_hashes_split_and_visible_citation_registry() -> None:
    root = _release_root()
    manifest = PublicBenchmarkManifestV3.model_validate_json((root / "manifest.json").read_bytes())
    assert manifest.metric_code_sha256 == scorer_code_sha256(root)
    for item in manifest.files:
        raw = (root / item.relative_path).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == item.file_sha256

    dev_families = {item.family_id for item in manifest.cases if item.split == "public_dev"}
    test_families = {item.family_id for item in manifest.cases if item.split == "hidden_test"}
    assert len(dev_families) == 11
    assert len(test_families) == 17
    assert not dev_families.intersection(test_families)

    forbidden = {
        "acceptance_contract",
        "active_when",
        "expected_document_states",
        "hidden_ground_truth",
        "path_probes",
        "reference_answer",
        "scenario",
        "selected_path",
    }
    for case in manifest.cases:
        registry = json.loads((root / case.source_registry_path).read_text(encoding="utf-8"))
        assert registry["case_id"] == case.case_id
        assert registry["registry_sha256"] == digest_json(
            {key: value for key, value in registry.items() if key != "registry_sha256"}
        )
        serialized = json.dumps(registry, sort_keys=True)
        assert all(f'"{key}"' not in serialized for key in forbidden)
        if case.split != "public_dev":
            continue
        assert case.public_gold_path is not None
        gold = json.loads((root / case.public_gold_path).read_text(encoding="utf-8"))
        contract = AcceptanceContract.model_validate(gold["acceptance_contract"])
        visible = {digest_json(item["locator"]) for item in registry["entries"]}
        required_document_ids = {
            document_id
            for evidence in contract.evidence_contracts
            for document_id in evidence.expected_document_states
        }
        required_locators = [
            locator
            for concept in contract.concepts
            if concept.requirement is Requirement.MANDATORY
            or concept.concept_id in required_document_ids
            for locator in concept.source_requirements
        ] + [
            locator
            for predicate in contract.branch_predicates
            for locator in predicate.source_requirements
        ]
        assert required_locators
        assert all(
            digest_json(locator.model_dump(mode="json")) in visible for locator in required_locators
        )


def test_public_baseline_validator_dev_scorer_and_hidden_interface(tmp_path: Path) -> None:
    root = _release_root()
    manifest = PublicBenchmarkManifestV3.model_validate_json((root / "manifest.json").read_bytes())
    submission = tmp_path / "alias-rule-dev.jsonl"
    digest = write_alias_rule_baseline(root=root, output=submission)
    assert digest == hashlib.sha256(submission.read_bytes()).hexdigest()
    candidates = load_submission(
        path=submission,
        manifest=manifest,
        split="public_dev",
    )
    assert len(candidates) == 60
    score = score_dev(root=root, submission=submission)
    assert score["case_count"] == 60
    assert score["evaluation_failure_case_count"] == 0
    assert score["metrics"]
    assert all(item["denominator"] == 60 for item in score["metrics"].values())
    hidden = verify_hidden_protocol(root)
    assert hidden["hidden_case_count"] == 90
    assert hidden["test_gold_files_exposed"] is False


def test_state_stress_track_is_complete_and_executable(tmp_path: Path) -> None:
    root = _release_root()
    top = PublicBenchmarkManifestV3.model_validate_json((root / "manifest.json").read_bytes())
    manifest = StateStressManifestV3.model_validate_json(
        (root / "state-stress/manifest.json").read_bytes()
    )
    assert top.state_stress_manifest_sha256 == manifest.manifest_sha256
    assert len(manifest.variants) == 48
    predictions = build_state_stress_missing_floor_v3(root)
    submission = tmp_path / "state-stress-floor.jsonl"
    submission.write_bytes(
        b"".join(
            json.dumps(
                {
                    "stress_case_id": prediction.stress_case_id,
                    "prediction": prediction.model_dump(mode="json"),
                },
                allow_nan=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
            + b"\n"
            for prediction in predictions
        )
    )
    score = score_state_stress_dev_v3(root, submission)
    assert score["case_count"] == 24
    assert set(score["by_variant"]) == {
        "add_sufficient_artifact",
        "deactivate_requirement",
        "defer_conditional_requirement",
        "resolve_all_active_requirements",
    }


@pytest.mark.parametrize(
    "raw",
    (
        b'{"case_id":"x","case_id":"x","candidate":{}}\n',
        b'{"case_id":"x","candidate":{"confidence":NaN}}\n',
    ),
)
def test_submission_parser_rejects_non_strict_json(tmp_path: Path, raw: bytes) -> None:
    root = _release_root()
    manifest = PublicBenchmarkManifestV3.model_validate_json((root / "manifest.json").read_bytes())
    submission = tmp_path / "invalid.jsonl"
    submission.write_bytes(raw)
    with pytest.raises(PublicLeaderboardError):
        load_submission(path=submission, manifest=manifest, split="public_dev")
