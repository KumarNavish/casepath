#!/usr/bin/env python3
"""Bind fresh candidate/capture inputs to prepared helper sources only.

This helper runs after the product commit and a fresh final-source fixture
capture. It writes hash/timing expectations; it never runs a test, capture,
provider, deployment, integration, or publication operation. Missing inputs
fail before any binding file is written. Historical success receipts cannot
be substituted for the exact new source or final capture.
"""
from __future__ import annotations

if not __debug__:
    raise RuntimeError("Assertions must remain enabled")

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
ROOT = Path("/Users/kumar0002/Documents/Die Mobiliar/.work/casepath-commander-documentary-20261024")
NS = ROOT / ".runtime/documentary-release-20261025"
REL = NS / "release"
EV = ROOT / ".runtime/cinema-evidence"
BASE = "5da3233a0aa04ad29843c8ec55dfb685118381c9"
BRANCH = "codex/casepath-documentary-20261025"
PREVIOUS = "5da3233a0aa04ad29843c8ec55dfb685118381c9"
ASSETS = {
    "autonomous-language-v1.js", "autonomous-presentation-v1.js",
    "autonomous-workspace-v1.js", "autonomous-workspace-v1.css",
}
ACTS = ["customer", "reading", "process", "decision", "learning", "cases"]
API_HELPERS = {
    "integrate_canonical.py", "run_api_release.py", "renew_seed.py",
    "update_api_env.py", "deploy_api.py", "await_api.py", "require_completed_gate.py",
}
RELEASE_HELPERS = API_HELPERS | {
    "copy_sites_inputs.py", "run_sites_workflow_finite.py", "readback.py",
    "verify_readback.py", "verify_api_build_v2.py", "verify_public_image.py",
    "published_soak.py", "prepare_public_archive_transfer_v2.py",
    "verify_published.mjs", "verify_supplement.mjs",
}


def regular(path):
    path = Path(path)
    assert path.is_absolute() and ".." not in path.parts, str(path)
    assert path.is_relative_to(ROOT), str(path)
    assert path.is_file() and not path.is_symlink(), str(path)
    for parent in path.parents:
        assert not parent.is_symlink(), str(parent)
        if parent == ROOT:
            break
    return path


def digest(path):
    return hashlib.sha256(regular(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(regular(path).read_bytes())


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", type=Path, required=True,
                        help="Fresh post-commit local capture-receipt.json within this clone")
    parser.add_argument("--helper-review", type=Path,
                        help="Fresh explicit review of capture-helper diagnostics changed after adaptation")
    args = parser.parse_args()
    assert Path(__file__).resolve() == NS / "bind_documentary_runtime.py"
    capture_path = args.capture
    assert capture_path.is_absolute() and capture_path.is_relative_to(EV)
    assert capture_path.name == "capture-receipt.json"
    prerequisites = [
        NS / "documentary-helper-adaptation.json", NS / "source-binding.json",
        NS / "authored-files.json", NS / "independent-review.json",
        NS / "seal-candidate.json", NS / "prepare-candidate.json",
        NS / "require_completed_gate.py", capture_path, capture_path.parent / "timeline.json",
        REL / "release-helper-adaptation.json",
        *[REL / name for name in sorted(RELEASE_HELPERS)],
    ]
    missing = [str(path) for path in prerequisites if not path.is_file()]
    if missing:
        raise FileNotFoundError("Fresh documentary inputs are required before binding:\n" + "\n".join(missing))
    for path in prerequisites:
        regular(path)

    adaptation = read(NS / "documentary-helper-adaptation.json")
    assert adaptation["contract"] == "casepath.documentary-helper-adaptation/1"
    assert adaptation["root"] == str(ROOT) and adaptation["branch"] == BRANCH
    assert adaptation["base_commit"] == BASE and adaptation["previous_deployed_source"] == PREVIOUS
    assert adaptation["source_helpers_only"] is True
    assert adaptation["commands_executed"] is False and adaptation["success_receipts_copied"] is False
    release_adaptation = adaptation["release_adaptation"]
    assert regular(release_adaptation["path"]) == REL / "release-helper-adaptation.json"
    assert digest(release_adaptation["path"]) == release_adaptation["sha256"]
    changed_helpers = {
        relative: {"adapted_sha256": row["sha256"], "sha256": digest(ROOT / relative)}
        for relative, row in adaptation["helpers"].items()
        if digest(ROOT / relative) != row["sha256"]
    }
    allowed_capture_changes = {".runtime/cinema-evidence/capture.cjs", ".runtime/root-before/capture.cjs"}
    assert set(changed_helpers) <= allowed_capture_changes, "Unreviewed release helper drift: " + str(set(changed_helpers) - allowed_capture_changes)
    helper_review = None
    if changed_helpers:
        if args.helper_review is None:
            raise FileNotFoundError("Changed capture diagnostics require --helper-review before binding: " + str(sorted(changed_helpers)))
        helper_review = read(args.helper_review)
        assert helper_review["contract"] == "casepath.documentary-helper-review/1"
        assert helper_review["base_commit"] == BASE and helper_review["branch"] == BRANCH
        assert helper_review["status"] == "passed" and helper_review["blocking_findings"] == []
        assert isinstance(helper_review["reviews"], list) and helper_review["reviews"]
        assert all(isinstance(item, dict) and item.get("reviewer") and item.get("verdict") for item in helper_review["reviews"])
        assert set(helper_review["reviewed_helpers"]) == set(changed_helpers)
        for relative, actual in changed_helpers.items():
            reviewed = helper_review["reviewed_helpers"][relative]
            assert reviewed["adapted_sha256"] == actual["adapted_sha256"]
            assert reviewed["sha256"] == actual["sha256"] and reviewed.get("reason")
    else:
        assert args.helper_review is None, "No changed helpers; do not attach unrelated prior review"
    assert digest(__file__) == adaptation["generated_helpers"][".runtime/documentary-release-20261025/bind_documentary_runtime.py"]["sha256"]
    assert set(row["target_name"] for row in adaptation["release_helpers"].values()) == RELEASE_HELPERS

    source = read(NS / "source-binding.json")
    assert source["base_commit"] == BASE and source["branch"] == BRANCH
    sha = source["source_commit"]
    assert re.fullmatch("[0-9a-f]{40}", sha) and sha not in {BASE, PREVIOUS}
    helper_review_input = None
    if helper_review is not None:
        assert helper_review["source_commit"] == sha
        helper_review_input = {"path": str(regular(args.helper_review)), "sha256": digest(args.helper_review)}
    # The shared validator imports without operations. Its validation performs
    # read-only Git/hash checks and rechecks the fresh independent-review inputs.
    from require_completed_gate import verify_source
    manifest = verify_source(source)
    assert source["source_files"] == len(manifest["files"]) == 1746
    assert read(NS / "seal-candidate.json")["status"] == "passed"
    prepared = read(NS / "prepare-candidate.json")
    assert prepared["source_commit"] == sha and prepared["exit_code"] == 0
    authored = read(NS / "authored-files.json")
    authored = authored["files"] if isinstance(authored, dict) else authored
    assert set(authored) == set(source["authored_sha256"])
    assert len(authored) == len(set(authored))

    capture = read(capture_path)
    assert capture["status"] == "passed" and capture["source_commit"] == sha
    assert capture["mode"] == "recorded_fixture_replay" and capture["new_inference"] is False
    assert capture["browser_errors"] == capture["unexpected_destinations"] == capture["writes"] == []
    assert set(capture["asset_sha256"]) == ASSETS
    for name, expected in capture["asset_sha256"].items():
        assert re.fullmatch("[0-9a-f]{64}", expected)
        assert digest(ROOT / "casepath/assets" / name) == expected
        relative = "casepath/assets/" + name
        if relative in source["authored_sha256"]:
            assert source["authored_sha256"][relative] == expected
    assert {"casepath/assets/autonomous-presentation-v1.js",
            "casepath/assets/autonomous-workspace-v1.js",
            "casepath/assets/autonomous-workspace-v1.css"} <= set(source["authored_sha256"])
    timeline = capture["timeline"]
    assert read(capture_path.parent / "timeline.json") == timeline
    duration = timeline["duration"]
    fps = capture["fps"]
    assert type(duration) is int and duration == 98550, "Planned timeline changed; review the release contract"
    assert type(fps) is int and fps == 30
    frame_count = math.ceil(duration * fps / 1000)
    assert capture["frame_count"] == frame_count == 2957
    assert abs(capture["duration"] - frame_count / fps) < 1e-6
    assert [row["id"] for row in timeline["acts"]] == ACTS
    assert capture["output"] == {"width": 1920, "height": 1080}
    assert len(capture["frames"]) == 24
    assert 48000 % fps == 0
    expectation = {
        "source_commit": sha, "source_tree": source["source_tree"],
        "source_manifest_sha256": source["source_manifest_sha256"],
        "duration_ms": duration, "fps": fps, "frame_count": frame_count,
        "audio_sample_rate": 48000, "audio_pcm_samples": frame_count * (48000 // fps),
        "encoded_duration_seconds": frame_count / fps, "acts": ACTS,
        "asset_sha256": capture["asset_sha256"],
        "capture_receipt_sha256": digest(capture_path), "capture_receipt_path": str(capture_path),
        "timeline_sha256": digest(capture_path.parent / "timeline.json"),
        "capture_helper_sha256": digest(EV / "capture.cjs"),
        "fixture_capture_helper_sha256": digest(ROOT / ".runtime/root-before/capture.cjs"),
        "scope": "Exact timing and assets derived from this candidate's fresh final-source local capture; no public acceptance claimed.",
    }
    hashes = {name: digest(REL / name) for name in sorted(RELEASE_HELPERS)}
    final = {
        "source_commit": sha, "scope": "Runtime helper hashes only; no gate completion or publication claimed.",
        "helpers": hashes, "api_helpers": {name: hashes[name] for name in sorted(API_HELPERS)},
        "actual_gate_validator_sha256": digest(NS / "require_completed_gate.py"),
        "adaptation_sha256": digest(NS / "documentary-helper-adaptation.json"),
        "source_binding_sha256": digest(NS / "source-binding.json"),
        "helper_review_input": helper_review_input,
        "reviewed_helper_changes": changed_helpers,
    }
    expectation_bytes = encoded(expectation)
    acceptance = {
        "source_commit": sha,
        "scope": "Actual helper hashes and fresh local timing expectation only; no public success claimed.",
        "helpers": {**hashes, "presentation-expectation.json": hashlib.sha256(expectation_bytes).hexdigest()},
        "acceptance_runner_sha256": digest(NS / "run_published_acceptance.py"),
        "actual_gate_validator_sha256": digest(NS / "require_completed_gate.py"),
        "adaptation_sha256": digest(NS / "documentary-helper-adaptation.json"),
        "helper_review_input": helper_review_input,
    }
    outputs = {
        REL / "presentation-expectation.json": expectation_bytes,
        REL / "helper-final-binding.json": encoded(final),
        REL / "helper-acceptance-binding.json": encoded(acceptance),
    }
    # Check every output before writing any. Exact identical reruns can recover
    # an interrupted source-binding preparation; differing files fail closed.
    for path, raw in outputs.items():
        if path.exists():
            assert regular(path).read_bytes() == raw, "Reconcile different existing binding: " + str(path)
    verify_source(source)
    assert digest(capture_path) == expectation["capture_receipt_sha256"]
    for name, expected in hashes.items():
        assert digest(REL / name) == expected
    for relative, row in adaptation["helpers"].items():
        expected = changed_helpers.get(relative, row)["sha256"]
        assert digest(ROOT / relative) == expected
    if helper_review_input:
        assert digest(helper_review_input["path"]) == helper_review_input["sha256"]
    for path, raw in outputs.items():
        if not path.exists():
            with path.open("xb") as stream:
                stream.write(raw)
    print(json.dumps({"status": "inputs_bound_only", "source_commit": sha,
                      "duration_ms": duration, "frame_count": frame_count,
                      "gate_completion_claimed": False, "publication_claimed": False,
                      "bindings": {path.name: hashlib.sha256(raw).hexdigest() for path, raw in outputs.items()}}, indent=2))


if __name__ == "__main__":
    main()
