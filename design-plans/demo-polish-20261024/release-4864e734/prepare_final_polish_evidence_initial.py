"""Assemble the completed demo-polish evidence; never commit, push or deploy.

Install at NEW_NS/prepare_final_polish_evidence.py and use Python -I -B.
Required argument: --standard-verified <absolute standard-promotion/.../verify/receipt.json>.
Every operation before creating the fresh bundle is a read-only validation.
The input reviews must already have been authored by their actual reviewers.
This program neither invents a verdict nor changes a pending review to passed.
"""
from __future__ import annotations

if not __debug__:
    raise RuntimeError("Assertions required; do not use Python -O")

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import struct
import subprocess
import sys

sys.dont_write_bytecode = True
ROOT = Path("/Users/kumar0002/Documents/Die Mobiliar/.work/casepath-commander-demo-polish-clone-20261024")
NS = ROOT / ".runtime/commander-demo-polish"
BASE = NS / "release"
OLD_ROOT = ROOT.parent / "casepath-commander-northstar-20261024"
OLD_NS = OLD_ROOT / ".runtime/commander-northstar"
SHA = "4864e7347c299bf1b580a5b35667635bc1c47f15"
PREVIOUS = "b20685d1670b33b941b1bfcb902638a879c01b93"
MANIFEST_SHA = "4bbdb036e69777937f19647f55fca80896ad96ae971a43928220bf93a5ddedef"
SITE = "https://casepath-autonomous.kumarnavish.chatgpt.site"
API = "https://casepath-agent.fastapicloud.dev"
PROJECT = "appgprj_6ac8aab031988191b5c370f7a4dbf160"
BROWSER = BASE / ("published-browser-" + SHA[:8])
SOAK = BASE / ("published-soak-" + SHA[:8])
FILM = BASE / "public-film-review"
CAPTURE = BASE / "eight-state-capture"
FIDELITY = BASE / "northstar-fidelity"
OPENING = NS / "opening-published-4864"
BUNDLE = NS / "final-evidence-bundle"
INTENDED_DESTINATION = "design-plans/demo-polish-20261024/release-4864e734"
QUALIFIED_REVIEW = "../../northstar-review-20261024/OPERATOR_REVIEW.md"
STATES = (
    "state-1-ready.png", "state-2-source-opened.png", "state-3-exact-passage.png",
    "state-4-source-bound-fact.png", "state-5-accepted-question.png",
    "state-6-completed-process.png", "state-7-direct-edit.png", "state-8-later-case-reuse.png",
)
CONCEPTS = ("01-decision-building.png", "02-completed-process.png", "03-reviewed-memory-payoff.png")
PRESEAL_PNGS = (
    "preparing-desktop.png", "preparing-mobile.png", "admitted-intro-desktop.png",
    "invalid-state-desktop.png", "invalid-state-mobile.png",
)
PRESEAL_SOURCE_FILES = {
    "casepath-qa/autonomous-presentation-browser-v1.test.cjs",
    "casepath-qa/autonomous-workspace-v1.test.cjs",
    "casepath-qa/review-northstar-browser-v1.test.cjs",
    "casepath-qa/review-northstar-v1.test.cjs",
    "casepath/assets/autonomous-workspace-v1.css",
    "casepath/assets/autonomous-workspace-v1.js",
    "casepath/assets/review-northstar-v1.css",
    "casepath/assets/review-northstar-v1.js", "casepath/index.html",
}
RELEASE_HELPERS = (
    "integrate_canonical.py", "run_api_release.py", "renew_seed.py", "update_api_env.py",
    "deploy_api.py", "await_api.py", "require_completed_gate.py", "copy_sites_inputs.py",
    "run_sites_workflow_finite.py", "readback.py", "published_soak.py",
    "verify_published.mjs", "verify_supplement.mjs", "verify_public_image.py",
    "verify_api_build.py", "verify_readback.py", "capture_eight_states.mjs",
    "decode_public_film.py", "make_film_contact_sheet.mjs", "measure_northstar_fidelity.py",
    "resume_promoted_review_qa.py", "verify_promoted_review_qa.py",
)
NAMESPACE_HELPERS = (
    "seal_candidate.py", "commit_prepare.py", "run_full_gate.py", "require_completed_gate.py",
    "adopt_gate_browser.py", "run_published_acceptance.py", "run_northstar_artifacts.py",
    "promote_standard_workspace.py", "measure_public_opening_v2.mjs",
    "capture_opening_v2.cjs", "prepare_final_polish_evidence.py",
)
EXTRA_SOURCES = {
    ROOT / "casepath/source-manifest.json",
    OLD_NS / "engineering-demo/owner.json",
    OLD_NS / "engineering-demo/data-copy.json",
    OLD_NS / "engineering-demo/current-server.json",
    OLD_NS / "sealed-browser/receipt.json",
}


def now():
    return datetime.now(timezone.utc).isoformat()


def regular(path):
    path = Path(path)
    assert path.is_absolute() and ".." not in path.parts
    assert path.is_file() and not path.is_symlink(), str(path)
    anchor = NS if path.is_relative_to(NS) else ROOT.parent
    for candidate in path.parents:
        assert not candidate.is_symlink(), str(candidate)
        if candidate == anchor:
            break
    return path


def digest(path):
    path = regular(path)
    before = path.stat()
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    after = path.stat()
    assert (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) == (
        after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns), str(path)
    return value.hexdigest()


def read(path):
    return json.loads(regular(path).read_bytes())


def encoded(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def json_safe(value):
    """Reject secret-bearing or native payload fields in otherwise allowed JSON."""
    if isinstance(value, dict):
        assert not str(value.get("contract", "")).startswith("casepath.local-runtime-boot/"), "Do not copy native boot payloads"
        for key, child in value.items():
            normalized = key.lower().replace("-", "_")
            assert normalized not in {
                "authorization", "api_key", "access_token", "refresh_token", "client_secret",
                "password", "secret_value", "seed_base64", "payload_base64", "workspace_base64",
            }, "Sensitive JSON field: " + key
            assert not (normalized.endswith(("_base64", "_b64")) and isinstance(child, str)), key
            assert not (normalized == "journal_rows" and isinstance(child, list)), "Raw journal payload"
            json_safe(child)
    elif isinstance(value, list):
        for child in value:
            json_safe(child)


def png(path, dimensions=None):
    with regular(path).open("rb") as stream:
        header = stream.read(24)
    assert header[:8] == b"\x89PNG\r\n\x1a\n" and header[12:16] == b"IHDR"
    observed = struct.unpack(">II", header[16:24])
    assert all(value > 0 for value in observed)
    if dimensions is not None:
        assert observed == dimensions, (str(path), observed)
    return observed


def exact_terminal(path, session):
    actual = read(path)  # Parent preserves structuredContent.result, not an operation envelope.
    assert actual["sessionId"] == session and actual["state"] == "completed"
    assert type(actual["exitCode"]) is int and actual["exitCode"] == 0
    return actual


def bound(item):
    path = regular(item["path"])
    assert path.is_relative_to(NS), str(path)
    assert digest(path) == item["sha256"], str(path)
    return path


class Plan:
    def __init__(self):
        self.copies = {}
        self.omitted = []

    def add(self, path, *, expected=None, target=None, authority=None):
        path = regular(path)
        assert path.is_relative_to(NS) or path in EXTRA_SOURCES, "Not an allowed evidence location: " + str(path)
        assert path.name not in {"readback-before.json", "readback-after.json", "api-build-log.json", "baseline-binding.json"}
        assert not path.is_relative_to(CAPTURE / "inputs"), "Raw public trace inputs are validated in place, not copied"
        assert not any(part in path.name.lower() for part in ("hosted-read-seed", ".sqlite", ".tar.", ".b64"))
        actual = digest(path)
        if expected is not None:
            assert actual == expected, str(path)
        name = target or path.relative_to(NS).as_posix()
        relative = PurePosixPath(name)
        assert str(relative) == name and not relative.is_absolute() and ".." not in relative.parts
        if path.suffix == ".json":
            json_safe(read(path))
        row = {"file": name, "source_path": str(path), "original_sha256": actual,
               "bytes": path.stat().st_size,
               "hash_authority": authority or "Exact source bytes rechecked by this evidence generator"}
        if name in self.copies:
            assert self.copies[name]["original_sha256"] == actual and self.copies[name]["source_path"] == str(path)
        else:
            self.copies[name] = row
        return row

    def omit(self, path, expected, reason):
        path = regular(path)
        assert path.is_relative_to(NS) and digest(path) == expected
        self.omitted.append({"source_path": str(path), "sha256": expected, "bytes": path.stat().st_size,
                             "copied": False, "reason": reason})


def validate_preseal(plan, binding):
    for key in ("independent_review", "preseal_browser_receipt", "authored_files_input"):
        item = binding[key]
        plan.add(bound(item), expected=item["sha256"], authority="source-binding.json:" + key)
    review = read(binding["independent_review"]["path"])
    assert review["status"] == "passed" and review["blocking_findings"] == []
    assert review["reviewed_source_files"] == binding["authored_sha256"]
    original = read(binding["preseal_browser_receipt"]["path"])
    assert original["status"] == "passed" and original["browser_errors"] == original["unexpected_destinations"] == []
    command_path = NS / "preseal-opening-final-command.json"
    command = read(command_path)
    visual_path = NS / "opening-visual-2/receipt.json"
    visual = read(visual_path)
    visual_binding_path = NS / "preseal-visuals.json"
    visual_binding = read(visual_binding_path)
    assert visual_binding["source_commit"] == SHA and visual_binding["status"] == "visually_reviewed"
    assert visual_binding["reviewer_kind"] == "assistant" and visual_binding["reviewed_before_seal"] is True
    assert visual_binding["command_receipt_sha256"] == digest(command_path)
    assert visual_binding["browser_receipt_sha256"] == command["visual_receipt_sha256"] == digest(visual_path)
    assert command["status"] == "passed" and command["exit_code"] == 0
    assert set(command["source_files"]) == PRESEAL_SOURCE_FILES
    assert command["source_files"] == {name: binding["authored_sha256"][name] for name in PRESEAL_SOURCE_FILES}
    assert review["preseal_opening_command_sha256"] == digest(command_path)
    assert review["preseal_opening_visual_receipt_sha256"] == digest(visual_path)
    assert review["visual_review"]["root_inspected"] is True
    assert review["visual_review"]["mobile_failure_explanation_scroll"].strip()
    assert command["commands"] and all(row["exit_code"] == 0 for row in command["commands"])
    assert visual["completed"] is True
    assert all(visual[key] == [] for key in ("writes", "pageErrors", "consoleErrors", "missingFixtures"))
    assert [row["file"] for row in visual["frames"]] == list(PRESEAL_PNGS)
    assert command["visual_checks"] == visual["visualChecks"]
    assert all(row["noHorizontalOverflow"] is True and row["headingsFullyVisible"] is True for row in visual["visualChecks"])
    for relative, expected in visual["sourceHashes"].items():
        assert digest(ROOT / relative) == expected, relative
    assert len(visual_binding["files"]) == 5
    assert {Path(row["path"]).name for row in visual_binding["files"]} == set(PRESEAL_PNGS)
    frame_by_name = {frame["file"]: frame for frame in visual["frames"]}
    for row in visual_binding["files"]:
        frame = frame_by_name[Path(row["path"]).name]
        path = bound(row)
        assert path == visual_path.parent / frame["file"]
        png(path, (frame["viewport"]["width"], frame["viewport"]["height"]))
        plan.add(path, expected=row["sha256"], authority="preseal-visuals.json")
    plan.add(visual_binding_path)
    plan.add(command_path, expected=visual_binding["command_receipt_sha256"])
    plan.add(visual_path, expected=command["visual_receipt_sha256"])
    assert Path(command["log"]) == NS / "preseal-opening-final.log"
    plan.add(command["log"], expected=command["log_sha256"])
    # Earlier combined checks are development history. Their opening bytes
    # intentionally predate the final rail adjustment and are never rebound.
    earlier_path = NS / "preseal-candidate-command.json"
    earlier = read(earlier_path)
    assert digest(earlier_path) == review["preseal_review_command_sha256"]
    assert earlier["status"] == "passed" and earlier["exit_code"] == 0
    assert earlier["commands"] and all(row["exit_code"] == 0 for row in earlier["commands"])
    assert Path(earlier["log"]) == NS / "preseal-candidate.log"
    plan.add(earlier_path)
    plan.add(earlier["log"], expected=earlier["log_sha256"],
             authority="Earlier preseal command; not whole-final-source verification")
    counts = {}
    for name, receipt in (("earlier_combined", earlier), ("final_opening", command)):
        counts[name] = [int(value) for value in re.findall(r"^# pass ([0-9]+)\s*$", Path(receipt["log"]).read_text(), re.M)]
    return {"visual_binding": visual_binding, "visual": visual, "development_pass_counts": counts}


def validate_adoption(plan, binding, gate):
    path = NS / "sealed-browser-command.json"
    sealed = read(path)
    required = ("receipt.json", "source-review.png", "later-case-preview.png", "later-case-reuse.png",
                "mobile-review.png", "review-walkthrough.webm", "server.log")
    assert sealed["source_commit"] == SHA and sealed["source_tree"] == binding["source_tree"]
    assert sealed["source_manifest_sha256"] == MANIFEST_SHA
    assert sealed["status"] == "passed" and sealed["exit_code"] == 0 and sealed["source_clean_after"] is True
    assert sealed["copied_byte_identically"] is True
    assert sealed["execution_origin"] == "Mandatory review browser suite within the completed fresh full release gate; no second browser execution"
    assert sealed["gate_command_sha256"] == digest(NS / "full-gate-command.json")
    assert sealed["gate_proof_sha256"] == digest(BASE / "full-gate-verified.json")
    assert sealed["gate_actual_completion_sha256"] == digest(BASE / "gate-actual-completion.json")
    assert sealed["runner_sha256"] == digest(NS / "adopt_gate_browser.py")
    command = read(NS / "full-gate-command.json")
    assert sealed["gate_session_id"] == command["commander_session_id"]
    assert command["environment"]["CASEPATH_REVIEW_EVIDENCE_DIR"] == sealed["original_artifact_directory"] == str(NS / "gate-browser")
    assert sealed["out"] == str(NS / "sealed-browser") and set(sealed["artifact_hashes"]) == set(required)
    assert "review-northstar-browser-v1.test.cjs" in gate["frontend_suites_required"]
    for name in required:
        expected = sealed["artifact_hashes"][name]
        assert digest(NS / "gate-browser" / name) == expected
        plan.add(NS / "sealed-browser" / name, expected=expected, authority="sealed-browser-command.json:" + name)
    qa = read(NS / "sealed-browser/receipt.json")
    assert qa["status"] == "passed" and qa["browser_errors"] == qa["unexpected_destinations"] == []
    assert qa["mobile"] == {"pageOverflow": 0, "panelOverflow": 0, "reduced": True, "animations": 0}
    applied = next(row for row in qa["stages"] if row["stage"] == "later-case-application")
    assert applied["target_facts_preserved"] and applied["target_source_bindings_preserved"]
    assert applied["pin"]["version"] == 1 and applied["impact"]["next_action_changed"] is False
    assert applied["impact"]["changed_requirement_document_types"] == []
    assert applied["full_process_keyboard_access"] is True and applied["original_reader_retained"] is True
    plan.add(path)
    return sealed, qa


def validate_public(plan):
    acceptance_path = BASE / "published-acceptance-sequence.json"
    acceptance = read(acceptance_path)
    exact_terminal(BASE / "commander-acceptance-terminal.json", "cp-polish-20261024-published-acceptance")
    plan.add(acceptance_path)
    plan.add(BASE / "commander-acceptance-terminal.json")
    for stage in acceptance["stages"]:
        assert stage["status"] == "completed" and stage["exit_code"] == 0
        plan.add(stage["log"], expected=stage["log_sha256"], authority="published-acceptance-sequence.json")
        for item in stage["artifacts"]:
            path = bound(item)
            if path.name == "readback-after.json":
                plan.omit(path, item["sha256"], "Full private collection readback; retain the verified public preservation summary")
            else:
                plan.add(path, expected=item["sha256"], authority="published-acceptance-sequence.json")
    details = read(BROWSER / "published-verification.json")
    browser = read(BROWSER / "summary.json")
    soak = read(SOAK / "summary.json")
    final = read(BASE / "readback-verified.json")
    film = details["film"]
    assert details["expected_commit"] == film["source_commit"] == SHA
    assert film["reached_end"] and film["four_x_seen"] and not film["errors"] and not film["writes"]
    assert film["duration_ms"] == 88050 and film["viewport"] == {"width": 1440, "height": 900}
    video = BROWSER / "public-walkthrough.webm"
    assert Path(film["video_path"]) == video and video.stat().st_size == film["video_bytes"]
    plan.add(video, expected=film["video_sha256"], authority="published-verification.json:film")
    api = read(BASE / "api-release-sequence.json")
    assert api["status"] == "passed" and api["source_commit"] == SHA
    assert api["gate_sha256"] == digest(BASE / "full-gate-verified.json")
    assert [row["name"] for row in api["stages"]] == ["seed", "environment", "deployment", "activation"]
    for row in api["stages"]:
        assert row["status"] == "completed" and row["exit_code"] == 0
        plan.add(row["log"], expected=row["log_sha256"], authority="api-release-sequence.json")
    wheel = read(BASE / "api-private-wheel-verified.json")
    assert wheel["canonical_commit"] == SHA and wheel["pillow_security_version"] == "13.0.0"
    assert wheel["exact_private_seed_installed"] is True
    seed = read(BASE / "seed-renewal-receipt.json")
    assert seed["deployment_commit"] == SHA and seed["input_commit"] == PREVIOUS
    assert seed["raw_records_and_sources_unchanged"] is True and seed["native_replay_and_full_fresh_atomic_proof"] is True
    assert seed["read_only"] is True and seed["requests"] == 1 and seed["retries"] == 0
    assert seed["sha256"] == wheel["private_seed_sha256"]
    # Only the small receipt is accessed; the private seed path is never opened.
    health = read(BASE / "api-health-after.json")
    assert health["source_commit"] == SHA and health["status"] == "ok"
    assert health["read_only"] is True and health["writable"] is False and health["storage"] == "remote_primary"
    deployment = read(BASE / "api-deployment-uploaded.json")
    build = read(BASE / "api-build-version.json")
    assert build["source_commit"] == deployment["source_commit"] == SHA
    assert build["deployment_id"] == deployment["deployment_id"]
    assert build["status"] == "passed" and build["pillow_version"] == "13.0.0"
    assert build["installation_line"] == "+ pillow==13.0.0" and build["build_log_command_exit"] == 0
    assert build["server_decoder_invoked"] is False
    raw_build_path = BASE / "api-build-log.json"
    assert digest(raw_build_path) == build["raw_build_log_sha256"]
    raw_build = read(raw_build_path)["data"]
    assert raw_build["deployment_id"] == deployment["deployment_id"] and raw_build["failed"] is False
    matches = [row for row in raw_build["logs"] if str(row.get("message", "")).strip() == build["installation_line"]]
    assert matches
    build_excerpt = {"source_commit": SHA, "deployment_id": deployment["deployment_id"],
                     "raw_build_log_sha256": digest(raw_build_path), "raw_build_log_copied": False,
                     "build_log_command_exit": 0, "failed": False,
                     "installation_messages": [str(row["message"]).strip() for row in matches],
                     "server_decoder_invoked": False}
    plan.omit(raw_build_path, build["raw_build_log_sha256"], "Retain exact version receipt and selected installation-line excerpt")
    image = read(BASE / "public-image-verified.json")
    assert image["script_sha256"] == digest(BASE / "verify_public_image.py")
    assert image["http_status"] == 200 and image["bytes"] == 201417
    assert image["sha256"] == "2ab3a31917da3787a4fc3e334b609afe2da52bba7a9bda1d9356b70215ce14c1"
    assert image["matches_sealed_original"] is True and image["local_pillow"] == "13.0.0"
    assert image["methods"] == ["GET"] and image["provider_calls"] == 0 and image["server_decoder_exercised"] is False
    saved = read(BASE / "sites-saved-version.json")
    deployed = read(BASE / "sites-deployment.json")
    workflow = read(BASE / "sites-workflow-result.json")
    assert saved["project_id"] == deployed["project_id"] == workflow["project_id"] == PROJECT
    assert deployed["status"] == "succeeded" and deployed["url"] == SITE
    assert deployed["version_id"] == saved["id"] == acceptance["site_version_id"]
    assert saved["version_number"] == acceptance["site_version_number"]
    assert deployed["id"] == acceptance["site_deployment_id"]
    assert saved["source"]["commit_sha"] == workflow["commit_sha"] == acceptance["distribution_commit"]
    integration = read(BASE / "canonical-integration.json")
    assert integration["canonical_commit"] == SHA and integration["status"] == "pushed_and_verified"
    for name in (
        "api-release-sequence.json", "api-private-wheel-verified.json", "seed-renewal-receipt.json",
        "api-health-after.json", "api-deployment-uploaded.json", "api-build-version.json",
        "sites-saved-version.json", "sites-deployment.json", "sites-workflow-result.json",
        "sites-inputs-verified.json", "canonical-integration.json", "helper-final-binding.json",
        "helper-acceptance-binding.json",
    ):
        plan.add(BASE / name)
    baseline_path = BASE / "baseline-binding.json"
    baseline = read(baseline_path)
    # These six values are direct top-level fields. The nested limits,
    # prior-budget and run-grant history is neither traversed nor exported.
    baseline_summary = {key: baseline[key] for key in (
        "source_commit_at_start", "readback_sha256", "claims", "collection_sha256",
        "knowledge_sha256", "primary_reads_required",
    )}
    baseline_summary["baseline_binding_sha256"] = digest(baseline_path)
    assert baseline_summary["source_commit_at_start"] == PREVIOUS
    assert baseline_summary["claims"] == final["claims"] == 159
    assert baseline_summary["collection_sha256"] == final["collection_sha256"]
    assert baseline_summary["knowledge_sha256"] == final["knowledge_sha256"]
    assert baseline_summary["primary_reads_required"] is True
    plan.omit(baseline_path, baseline_summary["baseline_binding_sha256"],
              "Full nested historical policy, prior-budget and run-grant history; only six selected top-level fields are exported")
    plan.omit(BASE / "readback-before.json", baseline["readback_sha256"], "Full private baseline collection; summary hashes only")
    return {"acceptance": acceptance, "browser": browser, "details": details, "soak": soak, "final": final,
            "saved": saved, "deployment": deployed, "api_deployment": deployment, "build_excerpt": build_excerpt,
            "baseline_summary": baseline_summary}


def validate_artifacts(plan, sealed):
    sequence_path = BASE / "northstar-artifacts-sequence.json"
    sequence = read(sequence_path)
    terminal_path = BASE / "commander-artifacts-terminal.json"
    exact_terminal(terminal_path, "cp-polish-20261024-northstar-artifacts")
    assert sequence["contract"] == "casepath.northstar-artifacts/2"
    assert sequence["source_commit"] == SHA and sequence["status"] == "passed"
    assert sequence["source_clean_before"] is True and sequence["source_clean_after"] is True
    assert sequence["product_changes"] is False and sequence["reused_prior_failed_artifacts"] is False
    assert sequence["qualified_human_approval"] == sequence["visual_verdict"] == "pending"
    inputs_path = BASE / "northstar-artifact-inputs.json"
    inputs = read(inputs_path)
    assert sequence["script_sha256"] == inputs["runner_sha256"] == digest(NS / "run_northstar_artifacts.py")
    assert sequence["helper_binding_sha256"] == digest(inputs_path)
    assert inputs["source_commit"] == SHA
    for key, path in {
        "source_binding_sha256": NS / "source-binding.json",
        "gate_validator_sha256": BASE / "require_completed_gate.py",
        "gate_proof_sha256": BASE / "full-gate-verified.json",
        "gate_actual_completion_sha256": BASE / "gate-actual-completion.json",
        "published_acceptance_sha256": BASE / "published-acceptance-sequence.json",
        "sealed_browser_command_sha256": NS / "sealed-browser-command.json",
        "sealed_browser_receipt_sha256": NS / "sealed-browser/receipt.json",
    }.items():
        assert inputs[key] == digest(path), key
    for name, expected in inputs["helpers"].items():
        assert name in RELEASE_HELPERS and digest(BASE / name) == expected
    assert [row["name"] for row in sequence["stages"]] == ["film_frames", "contact_sheet", "eight_states", "fidelity"]
    for row in sequence["stages"]:
        assert row["status"] == "completed" and row["exit_code"] == 0
        plan.add(row["log"], expected=row["log_sha256"], authority="northstar-artifacts-sequence.json")
        plan.add(bound(row["artifact"]), expected=row["artifact"]["sha256"], authority="northstar-artifacts-sequence.json")
    outputs = {}
    for row in sequence["outputs"]:
        path = bound(row)
        assert path.is_relative_to(FILM) or path.is_relative_to(CAPTURE) or path.is_relative_to(FIDELITY)
        assert path.stat().st_size == row["bytes"] and str(path) not in outputs
        outputs[str(path)] = row["sha256"]
    def artifact(path, expected=None):
        assert str(path) in outputs
        if expected is not None:
            assert outputs[str(path)] == expected
        return plan.add(path, expected=outputs[str(path)], authority="northstar-artifacts-sequence.json:outputs")
    for path in (sequence_path, terminal_path, inputs_path):
        plan.add(path)
    frames_path = FILM / "frames-index.json"
    frames = read(frames_path)
    assert frames["contract"] == "casepath.actual-film-cold-review/1"
    assert frames["source_commit"] == SHA and frames["status"] == "passed" and frames["decoded_frames"] == 24
    assert frames["script_sha256"] == digest(BASE / "decode_public_film.py")
    assert frames["helper_binding_sha256"] == digest(inputs_path)
    assert frames["published_browser_report_sha256"] == digest(BROWSER / "published-verification.json")
    assert Path(frames["video"]) == BROWSER / "public-walkthrough.webm"
    assert frames["video_sha256"] == digest(frames["video"])
    assert frames["video_bytes"] == Path(frames["video"]).stat().st_size
    assert frames["synthetic_or_seeked_browser_frames"] is False and frames["exact_video_pts_to_browser_clock_mapping_claimed"] is False
    assert frames["viewport"] == {"width": 1440, "height": 900}
    duration = frames["recorded_duration_seconds"]
    assert isinstance(duration, (int, float)) and math.isfinite(duration) and duration >= 88.05
    assert frames["playback_clock_observations"]["duration_ms"] == 88050
    assert len(frames["frames"]) == 24
    for number, frame in enumerate(frames["frames"], 1):
        assert frame["number"] == number and frame["file"] == f"cold-frame-{number:02d}.png"
        assert frame["at_seconds"] == round((number - 0.5) * duration / 24, 6)
        path = FILM / frame["file"]
        assert path.stat().st_size == frame["bytes"]
        png(path, (1440, 900))
        artifact(path, frame["sha256"])
    artifact(frames_path)
    artifact(FILM / "video-metadata.log")
    sheet_path = FILM / "contact-sheet.json"
    sheet = read(sheet_path)
    assert sheet["source_commit"] == SHA and sheet["status"] == "passed"
    assert sheet["script_sha256"] == digest(BASE / "make_film_contact_sheet.mjs")
    assert sheet["helper_binding_sha256"] == digest(inputs_path) and sheet["frame_index_sha256"] == digest(frames_path)
    assert sheet["source_frames"] == [{"number": row["number"], "sha256": row["sha256"]} for row in frames["frames"]]
    assert sheet["file"] == "film-contact-sheet.png"
    png(FILM / sheet["file"], (1520, 1606))
    assert (FILM / sheet["file"]).stat().st_size == sheet["bytes"]
    artifact(sheet_path)
    artifact(FILM / sheet["file"], sheet["sha256"])
    cold_path = FILM / "cold-viewer-review.json"
    cold = read(cold_path)
    assert cold["source_commit"] == SHA and cold["frame_index_sha256"] == digest(frames_path)
    assert cold["video_sha256"] == digest(BROWSER / "public-walkthrough.webm")
    assert cold["reviewed_frame_numbers"] == list(range(1, 25))
    assert cold["fresh_reviewer_without_project_history"] is True and cold["accepted_for_silent_film_clarity"] is True
    assert cold["reviewer_kind"] == "assistant"
    assert all(isinstance(cold["answers"].get(key), str) and cold["answers"][key].strip()
               for key in ("what_it_does", "how_it_reaches_results", "why_valuable", "what_was_unclear"))
    plan.add(cold_path, authority="Actual independent assistant review; qualification is not claimed")
    eight_path = CAPTURE / "eight-state-evidence.json"
    eight = read(eight_path)
    assert eight["contract"] == "casepath.eight-state-engineering-evidence/2"
    assert eight["source_commit"] == SHA and eight["status"] == "passed" and eight["errors"] == eight["writes"] == []
    assert eight["qualified_human_approval"] == "pending"
    assert eight["literal_state_8_expert_review_acceptance"] is False and eight["claim_outcome_authorized"] is False
    assert eight["script_sha256"] == digest(BASE / "capture_eight_states.mjs")
    assert eight["source_binding_sha256"] == digest(NS / "source-binding.json")
    assert eight["helper_binding_sha256"] == digest(inputs_path)
    assert eight["official_validator_sha256"] == digest(ROOT / "casepath/assets/autonomous-workspace-v1.js")
    admitted_path = CAPTURE / "admitted-manifest.json"
    admitted = read(admitted_path)
    assert digest(admitted_path) == eight["admitted_manifest_sha256"] and admitted == eight["manifest"]
    assert admitted["duration"] == 88050 and len(admitted["claims"]) == len(set(admitted["claims"])) == len(admitted["stateHashes"])
    assert [row["state"] for row in eight["states"]] == list(range(1, 9))
    assert [row["file"] for row in eight["states"]] == list(STATES)
    for row in eight["states"]:
        path = CAPTURE / row["file"]
        assert (row["width"], row["height"]) == (1440, 900) and path.stat().st_size == row["bytes"]
        png(path, (1440, 900))
        artifact(path, row["sha256"])
    assert eight["states"][4]["recorded_relationship"]["fact_count"] >= 2
    assert eight["states"][5]["observed"]["completed_process"] is True
    for number, name in ((7, "source-review.png"), (8, "later-case-reuse.png")):
        row = eight["states"][number - 1]
        assert row["sha256"] == sealed["artifact_hashes"][name]
        assert row["source_receipt_sha256"] == sealed["artifact_hashes"]["receipt.json"]
        assert row["actor"] == "Test handler — engineering QA" and row["qualified_human_approval"] is False
    trace_flags = (
        "official_readState_passed", "official_atomic_head_passed", "official_replay_start_passed",
        "official_checkedOperationBinding_passed", "official_checkedOperation_all_passed",
        "official_checkpoints_all_passed", "final_binding_verified", "admitted_state_hash_matched",
    )
    assert {row["claim_id"] for row in eight["live_trace_validations"]} == set(admitted["claims"])
    assert len(eight["live_trace_validations"]) == len(admitted["claims"])
    response_hashes = {}
    for row in eight["http_inputs"]:
        assert row["method"] == "GET" and row["status"] == 200
        relative = PurePosixPath(row["file"])
        assert relative.parts[0] == "inputs" and not relative.is_absolute() and ".." not in relative.parts
        path = CAPTURE / relative
        assert path.stat().st_size == row["bytes"] and outputs[str(path)] == row["sha256"]
        assert row["file"] not in response_hashes
        response_hashes[row["file"]] = row["sha256"]
        plan.omit(path, row["sha256"], "Fresh public response retained in runtime; package includes its bound validation receipt, not response bodies")
    for row in eight["live_trace_validations"]:
        assert all(row[key] is True for key in trace_flags)
        assert row["input_digest_independently_reconstructed"] is False
        for stem in ("trace", "claim", "opening", "snapshot"):
            assert response_hashes[row[stem + "_file"]] == row[stem + "_sha256"]
    artifact(eight_path)
    artifact(admitted_path)
    fidelity_path = FIDELITY / "fidelity-measurements.json"
    fidelity = read(fidelity_path)
    assert fidelity["source_commit"] == SHA and fidelity["status"] == "measured" and fidelity["visual_review"] == "pending"
    assert fidelity["script_sha256"] == digest(BASE / "measure_northstar_fidelity.py")
    assert fidelity["tool_sha256"] == digest(ROOT / "design-plans/tools/fidelity.mjs")
    assert fidelity["helper_binding_sha256"] == digest(inputs_path)
    assert fidelity["capture_receipt_sha256"] == digest(eight_path)
    assert [row["concept"] for row in fidelity["comparisons"]] == list(CONCEPTS)
    for ordinal, (row, state) in enumerate(zip(fidelity["comparisons"], (4, 6, 8)), 1):
        assert row["state"] == state and row["frame"] == STATES[state - 1]
        assert row["frame_sha256"] == digest(CAPTURE / row["frame"])
        assert row["concept_sha256"] == digest(ROOT / "design/northstar" / row["concept"])
        assert math.isfinite(row["mean_difference_pct"]) and 0 <= row["mean_difference_pct"] <= 100
        assert [item["kind"] for item in row["outputs"]] == ["side", "overlay", "diff"]
        for item in row["outputs"]:
            assert item["file"] == f"concept-{ordinal:02d}-{item['kind']}.png"
            path = FIDELITY / item["file"]
            png(path)
            assert path.stat().st_size == item["bytes"]
            artifact(path, item["sha256"])
        artifact(FIDELITY / f"concept-{ordinal:02d}-command.log", row["command_log_sha256"])
    artifact(fidelity_path)
    review_path = FIDELITY / "visual-review.json"
    review = read(review_path)
    assert review["source_commit"] == SHA and review["status"] == "passed" and review["pending"] == []
    assert review["measurement_sha256"] == digest(fidelity_path) and review["qualified_human_approval"] == "pending"
    assert len(review["comparisons"]) == 3 and {row["name"] for row in review["comparisons"]} == set(CONCEPTS)
    decisions = {row["name"]: row for row in review["comparisons"]}
    for measured in fidelity["comparisons"]:
        decision = decisions[measured["concept"]]
        assert decision["decision"] == "accepted_with_documented_deviations"
        assert isinstance(decision["justification"], str) and decision["justification"].strip()
        assert len(decision["reviewed_outputs"]) == 3
        assert {row["file"]: row["sha256"] for row in decision["reviewed_outputs"]} == {
            row["file"]: row["sha256"] for row in measured["outputs"]}
    plan.add(review_path, authority="Root-authored visual review after inspecting the actual comparison outputs")
    return {"frames": frames, "cold": cold, "eight": eight, "fidelity": fidelity, "fidelity_review": review}


def validate_opening(plan):
    path = OPENING / "receipt.json"
    opening = read(path)
    assert opening["source_commit"] == SHA and opening["status"] == "passed"
    assert type(opening["ready_at_ms"]) is int and opening["ready_at_ms"] > 0
    assert opening["errors"] == opening["application_writes"] == []
    assert isinstance(opening["opening"]["purpose"], str) and opening["opening"]["purpose"].strip()
    assert opening["snapshots"] and opening["requests"]
    assert all(row["method"] in ("GET", "HEAD") or row["path"].startswith("/cdn-cgi/") for row in opening["requests"])
    plan.add(path, authority="Separate cold-opening inspection, paused at admission")
    png(OPENING / "ready.png", (1440, 900))
    plan.add(OPENING / "ready.png",
             authority="Exact observed inspection image; producer does not put an image digest in its receipt, so this index binds the bytes")
    baseline_path = NS / "opening-baseline/recovered-timing.json"
    if baseline_path.exists():
        plan.add(baseline_path, authority="Historical first-active observation only; no completed exact baseline")
    return opening


def validate_engineering(plan, release_proof, helper):
    path = BASE / "engineering-promotion-verified-4864.json"
    verified = read(path)
    assert verified["contract"] == "casepath.owned-qa-source-promotion-verified/1"
    assert verified["status"] == "passed" and verified["source_commit"] == verified["target_source_commit"] == SHA
    assert verified["release_proof"] == release_proof
    for key in (
        "known_owned_previous_process_terminated", "actual_previous_terminal_observed",
        "promoted_process_observed_running", "get_only", "initial_owner_preserved",
        "initial_copy_receipt_preserved", "original_qa_files_unchanged", "same_data_root",
        "current_claim_and_work_data_unchanged", "source_and_target_views_unchanged",
        "display_assets_match_new_capsule", "original_application_retained",
    ):
        assert verified[key] is True, key
    assert verified["copied_or_reset_data"] is False and verified["seeded_or_replayed_work"] is False
    assert verified["qualified_human_approval_asserted"] is False
    assert verified["launcher_sha256"] == digest(BASE / "resume_promoted_review_qa.py")
    assert verified["verifier_sha256"] == digest(BASE / "verify_promoted_review_qa.py")
    current_path = OLD_NS / "engineering-demo/current-server.json"
    current = read(current_path)
    assert digest(current_path) == verified["current_server_sha256"] and current == verified["current_server"]
    before_path = bound(verified["checkpoint"])
    before = read(before_path)
    assert before["contract"] == "casepath.owned-qa-promotion-checkpoint/1" and before["status"] == "passed"
    assert before["data_fingerprints"] == current["data_before"] == current["data_after"] == verified["data_fingerprints"]
    assert before["views"] == current["views_before"] == current["views_after"] == verified["views"]
    previous_path = bound(verified["previous_current_server"])
    assert previous_path.is_relative_to(NS / "engineering-demo-promotions")
    assert digest(previous_path) == before["current_server_sha256"]
    assert read(previous_path) == before["current_server"]
    assert read(previous_path.parent / "owner.json") == current
    assert read(previous_path.parent / "before-snapshot.json") == before
    for key, predicate, field, session in (
        ("stop", lambda row: row.get("terminated") is True, "terminated", current["previous_session"]),
        ("terminal", lambda row: row.get("state") in ("completed", "terminated", "failed"), "state", current["previous_session"]),
        ("running", lambda row: row.get("state") == "running" and row.get("pid") == current["pid"], "state", current["commander_session"]),
    ):
        item = verified["commander_evidence"][key]
        _, observed = helper.commander_evidence(item["path"], session, predicate, observation_field=field)
        assert observed == item
        plan.add(bound(item), expected=item["sha256"], authority="engineering-promotion-verified-4864.json:" + key)
    proof = verified["original_proof"]
    for name, key in (("owner.json", "initial_owner_sha256"), ("data-copy.json", "initial_copy_sha256")):
        plan.add(OLD_NS / "engineering-demo" / name, expected=proof[key],
                 target="local-original-engineering/" + name, authority="engineering promotion original provenance")
    plan.add(OLD_NS / "sealed-browser/receipt.json", expected=proof["original_qa_receipt_sha256"],
             target="local-original-engineering/original-qa-receipt.json", authority="Original b206 QA store ancestry")
    plan.add(current_path, expected=verified["current_server_sha256"], target="local-engineering-current-server.json")
    plan.add(before_path, expected=verified["checkpoint"]["sha256"])
    plan.add(previous_path, expected=verified["previous_current_server"]["sha256"])
    plan.add(previous_path.parent / "owner.json")
    plan.add(previous_path.parent / "before-snapshot.json")
    plan.add(path)
    return verified


def validate_standard(plan, path, gate_completion):
    path = regular(path)
    assert path.is_relative_to(NS / "standard-promotion") and path.name == "receipt.json"
    assert path.parent.name == "verify"
    attempt = path.parent.parent
    assert re.fullmatch(r"[a-z][a-z0-9-]{0,79}", attempt.name)
    verified = read(path)
    snapshot_path, source_path = bound(verified["snapshot_receipt"]), bound(verified["source_receipt"])
    assert snapshot_path == attempt / "snapshot/receipt.json" and source_path == attempt / "source/receipt.json"
    snapshot, source = read(snapshot_path), read(source_path)
    helper_binding_path = attempt / "helper-binding.json"
    helper_binding = read(helper_binding_path)
    assert helper_binding["contract"] == "casepath.standard-promotion-helper/1"
    assert helper_binding["source_commit"] == SHA and helper_binding["old_source_commit"] == PREVIOUS
    assert helper_binding["helper_path"] == str(NS / "promote_standard_workspace.py")
    assert helper_binding["publication_helper_binding_modified"] is False
    for row, mode in ((snapshot, "snapshot"), (source, "source"), (verified, "verify")):
        assert row["contract"] == "casepath.standard-promotion/1" and row["status"] == "passed" and row["mode"] == mode
        assert row["source_commit"] == SHA and row["old_source_commit"] == PREVIOUS
        assert row["helper_sha256"] == helper_binding["helper_sha256"] == digest(NS / "promote_standard_workspace.py")
        assert row["source_binding_sha256"] == helper_binding["source_binding_sha256"] == digest(NS / "source-binding.json")
        assert row["helper_binding_sha256"] == digest(helper_binding_path)
    assert verified["snapshot_receipt"] == source["snapshot_receipt"]
    assert source["original_data_unchanged"] is True and source["native_boot_unchanged"] is True
    assert source["official_prepare_exit_code"] == 0
    for key in ("original_data_unchanged", "repeated_full_fingerprint_equal", "boot_lineage_advanced", "prior_boot_files_unchanged", "get_only"):
        assert verified[key] is True, key
    assert snapshot["get_only"] is True and snapshot["repeated_full_fingerprint_equal"] is True
    proof = verified["release"]
    assert source["release"] == proof and proof["completed_gate"] == gate_completion
    assert proof["gate_guard_sha256"] == digest(NS / "require_completed_gate.py")
    assert proof["published_acceptance_sha256"] == digest(BASE / "published-acceptance-sequence.json")
    assert proof["publication_helper_binding_sha256"] == digest(BASE / "helper-acceptance-binding.json")
    assert verified["data_fingerprint_sha256"] == hashlib.sha256(encoded(snapshot["data"])).hexdigest()
    old_boot, new_boot = snapshot["native_boot"], verified["native_boot"]
    boot_keys = {"current_sha256", "current_bytes", "current_immutable_file", "inventory", "inventory_sha256", "history_count", "identity"}
    for boot in (old_boot, new_boot):
        assert set(boot) == boot_keys, "Only sanitized native boot identity and inventory are admissible"
        assert boot["inventory_sha256"] == hashlib.sha256(encoded(boot["inventory"])).hexdigest()
        assert boot["history_count"] == len(boot["inventory"])
    assert old_boot["identity"]["source_commit"] == PREVIOUS
    assert new_boot["identity"]["source_commit"] == SHA and new_boot["identity"]["source_manifest_sha256"] == MANIFEST_SHA
    assert new_boot["identity"]["prior_boot_receipt_file_sha256"] == old_boot["current_sha256"]
    assert all(new_boot["inventory"].get(name) == row for name, row in old_boot["inventory"].items())
    assert sorted(set(new_boot["inventory"]) - set(old_boot["inventory"])) == [verified["added_immutable_boot"]] == [new_boot["current_immutable_file"]]
    assert new_boot["history_count"] == old_boot["history_count"] + 1
    assert verified["model_ledger"]["records"] == verified["model_ledger"]["network_calls"] == 0
    assert verified["health"]["identity"]["source_commit"] == SHA
    running = verified["commander_running"]
    assert running["state"] == "running" and len(running["pids"]) == 1
    actual = read(bound(running))
    assert actual["sessionId"] == running["sessionId"] and actual["state"] == "running" and actual["pid"] == running["pids"][0]
    assert actual["pid"] in verified["listener"]["ancestor_pids"]
    assert verified["listener"]["listener_pid"] == new_boot["identity"]["listener_pid"]
    plan.add(bound(running), expected=running["sha256"])
    stop = source["stop_evidence"]
    assert stop["actual_structured_stop_and_terminal"] is True
    plan.add(bound(stop), expected=stop["sha256"])
    assert len(source["commands"]) == 3
    for row, name in zip(source["commands"], ("fetch", "fast-forward", "official-prepare")):
        assert row["exit_code"] == 0 and Path(row["log"]) == attempt / "source" / (name + ".log")
        plan.add(row["log"], expected=row["log_sha256"], authority="standard source promotion command receipt")
        completed_path = attempt / "source" / (name + "-completed.json")
        assert read(completed_path) == row
        plan.add(completed_path)
        for suffix in ("requested", "started"):
            event_path = attempt / "source" / (name + "-" + suffix + ".json")
            event = read(event_path)
            assert event["command"] == row["command"] and event["log"] == row["log"]
            if suffix == "started":
                assert event["pid"] == row["pid"]
            plan.add(event_path)
    readiness = verified["readiness_observations"]
    assert Path(readiness["path"]) == path.parent / "readiness-observations.jsonl"
    plan.add(bound(readiness), expected=readiness["sha256"])
    assert len(verified["assets"]) == 6
    for row in verified["assets"]:
        source_asset = regular(row["source_path"])
        assert source_asset.parent == ROOT / "casepath/assets"
        assert Path(row["path"]) == path.parent / "assets" / source_asset.name
        assert row["sha256"] == row["source_sha256"] == digest(source_asset)
        assert Path(row["path"]).stat().st_size == row["bytes"]
        plan.add(bound(row), expected=row["sha256"], authority="standard promotion served source asset")
    for artifact in (helper_binding_path, snapshot_path, source_path, path):
        plan.add(artifact)
    return verified


def md(value):
    return str(value).replace("|", r"\|").replace("\r", "").replace("\n", " ")


def reports(binding, gate, public, artifacts, opening, engineering, standard, standard_path, preseal):
    saved, deployed, final, soak = public["saved"], public["deployment"], public["final"], public["soak"]
    release = {
        "contract": "casepath.demo-polish-release-acceptance/1", "prepared_at": now(),
        "tested_and_deployed_source": SHA, "source_tree": binding["source_tree"],
        "source_manifest_sha256": MANIFEST_SHA, "previous_deployed_source": PREVIOUS,
        "site_url": SITE, "site_version_id": saved["id"], "site_version_number": saved["version_number"],
        "site_deployment_id": deployed["id"], "distribution_commit": saved["source"]["commit_sha"],
        "api_url": API, "api_deployment_id": public["api_deployment"]["deployment_id"],
        "fresh_complete_gate": True, "pytest_passed": gate["passed"], "historical_skips": gate["skipped"],
        "mandatory_frontend_suites": len(gate["frontend_suites_required"]),
        "review_browser_execution_origin": "Completed fresh full gate; byte-identical adoption; no second browser execution",
        "published_acceptance_actual_terminal": {"sessionId": "cp-polish-20261024-published-acceptance", "exitCode": 0},
        "artifact_capture_actual_terminal": {"sessionId": "cp-polish-20261024-northstar-artifacts", "exitCode": 0},
        "public_read_only": True, "primary_reads_verified": final["primary_reads_verified"],
        "collection_unchanged": final["collection_unchanged"], "knowledge_unchanged": final["knowledge_unchanged"],
        "ledger_unchanged": final["ledger_unchanged"], "provider_calls_total": final["provider_calls"],
        "new_provider_workflows_started": 0, "original_nine_repeated": False,
        "public_film_duration_ms": 88050, "actual_decoded_frames": 24, "engineering_state_images": 8,
        "fidelity_image_count": 9, "cold_opening_ready_at_ms": opening["ready_at_ms"],
        "cold_opening_scope": "Separate inspection paused at admission; not the continuous film timing",
        "baseline_timing_scope": "Historical first-active observation only; no completed exact baseline comparison is claimed",
        "cold_viewer_kind": "independent assistant", "qualified_human_approval": "pending",
        "literal_state_8_expert_review_acceptance": False, "claim_outcome_authorized": False,
        "engineering_store_source_ancestry": PREVIOUS, "engineering_store_preserved": True,
        "engineering_verification_sha256": digest(BASE / "engineering-promotion-verified-4864.json"),
        "standard_store_preserved": True, "standard_boot_lineage_advanced": True,
        "standard_verification_sha256": digest(standard_path),
        "intended_repository_destination": INTENDED_DESTINATION,
        "repository_evidence_commit_created_by_this_helper": False, "product_changes": False,
    }
    source_link = "http://127.0.0.1:4194/?journey=review&view=northstar#claim=clm_f69b1747447bc221"
    target_link = "http://127.0.0.1:4194/?journey=review&view=northstar#claim=clm_0e538990cc6ba7ef"
    fidelity_decisions = {row["name"]: row for row in artifacts["fidelity_review"]["comparisons"]}
    fidelity_rows = "\n".join(
        f"| {md(measure['concept'])} | {measure['mean_difference_pct']:.4f}% | {md(fidelity_decisions[measure['concept']]['justification'])} |"
        for measure in artifacts["fidelity"]["comparisons"])
    cold = artifacts["cold"]["answers"]
    readme = f"""# CasePath demo polish — completed release evidence

**Tested and deployed source: {SHA}. Sites version {saved['version_number']}.**

[Public presentation]({SITE}/?present=1#autonomous/demonstration) · [Presenter and restart runbook](demo-operator-guide.md) · [Machine acceptance](release-acceptance.json) · [Hash index](evidence-manifest.json)

The public presentation explains its purpose while recorded cases are admitted, then starts automatically. The receiving-case Result checker presents the historical Before/After comparison immediately, with an optional disclosure for the full 12-node process and an ordinal marker for the affected step. These changes use the existing source, journal and saved-version authority.

The receiving case retains its own **30. Juni** and **31. Juli** notice passages and exact saved version 1, even though the source library also contains version 2. **Compare both complete notices** is the additional prerequisite. **Preserve challenge or extension deadline** remains the next protective action. The original evidence connection is retained. These are engineering observations from fictional cases; they do not authorize a claim outcome.

## Completed verification

| Evidence | Actual result |
|---|---|
| [Complete official gate](release/full-gate-verified.json) | {gate['passed']:,} passed; {gate['skipped']} exact historical skips; zero failures, errors, deselections or new skips |
| Mandatory frontend coverage | All {len(gate['frontend_suites_required'])} declared suites required |
| [Gate browser adoption](sealed-browser-command.json) | The completed gate produced the operator walkthrough; its seven adopted artifacts are byte-identical. No second browser execution is claimed |
| [Published acceptance](release/published-acceptance-sequence.json) | Actual Commander terminal completion with exit 0 |
| [Read soak](release/published-soak-{SHA[:8]}/summary.json) | {soak['successful_soak_requests']}/{soak['observed_soak_requests']} reads succeeded; zero soak 503s; zero runner retries or initiated provider calls |
| [Published browser](release/published-browser-{SHA[:8]}/summary.json) | 18 desktop and 9 mobile views; source identities, loaded assets, original-source delivery, overflow and write checks passed |
| Continuous public film | Six acts, 88.05 seconds, 4× indicator observed, actual end reached |
| [Cold-opening inspection](opening-published-4864/receipt.json) | Admission observed after {opening['ready_at_ms']:,} ms; separate inspection paused at admission; no application writes or browser errors |
| [Primary source preservation](release/readback-verified.json) | {final['claims']} claims; collection, knowledge and ledger unchanged; {final['provider_calls']} existing provider calls; original nine workflows were not repeated |
| [Public original image](release/public-image-verified.json) | Exact 201,417-byte original JPEG; local Pillow 13.0.0 decoding verified |
| [API build](release/api-build-version.json) | Actual hosted installation log includes Pillow 13.0.0; server-side image decoding is not claimed |
| [Engineering promotion](release/engineering-promotion-verified-4864.json) | Existing port-4194 store, original QA ancestry, current data and process views preserved while source advanced |
| [Standard promotion]({standard_path.relative_to(NS).as_posix()}) | Existing port-4173 data/provenance preserved; exactly one native boot appended to the original immutable lineage |

## Actual film and visual review

The [continuous public recording](release/published-browser-{SHA[:8]}/public-walkthrough.webm), [24 decoded frames](release/public-film-review/frames-index.json), and [independent assistant review](release/public-film-review/cold-viewer-review.json) describe the same video bytes. The samples span the actual recording, including loading time; no exact video-PTS-to-browser-clock mapping is claimed.

**Purpose understood:** {cold['what_it_does']}

**Mechanism understood:** {cold['how_it_reaches_results']}

**Value understood:** {cold['why_valuable']}

**Remaining clarity observations:** {cold['what_was_unclear']}

![24 actual decoded frames](release/public-film-review/film-contact-sheet.png)

The [eight state images](release/eight-state-capture/eight-state-evidence.json) combine six fresh read-only public presentation observations with two exact screenshots from the completed gate's deterministic operator journey. States 7–8 are explicitly **Test handler engineering QA**. Numeric fidelity measurements are retained separately from the root-authored visual review.

| Concept | Measured pixel difference | Actual reviewed deviation |
|---|---:|---|
{fidelity_rows}

[Nine comparison images and measurements](release/northstar-fidelity/fidelity-measurements.json) · [Root visual review](release/northstar-fidelity/visual-review.json)

## Preseal chronology

The [earlier combined development command](preseal-candidate-command.json) predates the final opening-rail adjustment. Its source hashes remain as originally observed. The [final opening command](preseal-opening-final-command.json) separately binds the final nine application and test files, admission regressions and five visual captures. The separately reviewed plan is included in the ten-file authored source binding. The completed full gate then covers the sealed release. Earlier evidence is not relabeled as a complete test of later bytes.

The invalid-state mobile capture records that the full purpose text extends below the viewport during ordinary vertical scrolling; its recovery controls remain visible. The [root-authored preseal visual review](preseal-visuals.json) retains that observation rather than rewriting the geometric result.

## Qualification and evidence scope

**Qualified human approval remains pending.** The assistant cold-viewer review, root visual review, typed Test handler actor and automated gates are engineering evidence. [The source-bound operator review]({QUALIFIED_REVIEW}) identifies the substantive decision still required before accepting the exact reusable prerequisite for real use.

The two local workspaces keep their separate original stores. The new gate's disposable QA data is not used as the ancestry of the retained engineering store. Current QA edits are preserved; neither promotion restores a historical 164-event screenshot state.

This bundle contains explicit evidence files, exact recordings/images, safe hashes and runtime helper source. It excludes private seed bytes, complete collection readbacks, full historical policy/budget records, full corpus copies, credentials and native boot payloads. The [selected baseline summary](baseline-preservation-summary.json) contains only six top-level identity/preservation fields and the original binding-file hash. Raw fresh public response bodies are validated in the runtime and represented here by their receipt hashes. This generator creates no Git commit, push, deployment or product-source change.
"""
    guide = f"""# CasePath presenter and restart runbook

Tested and deployed source: {SHA}

## Public demonstration

Open [the public presentation]({SITE}/?present=1#autonomous/demonstration). Its purpose appears while admission completes, then playback starts automatically. Do not wait for or click a manual Start control before admission. The six acts last 88.05 seconds and display the 4× indicator. Use the actual visible transport controls once available; pause on dense evidence or legal text when presenting.

The recorded cold-opening inspection observed admission after {opening['ready_at_ms']:,} ms and paused there. It is a separate measurement from the [continuous film](release/published-browser-{SHA[:8]}/public-walkthrough.webm). The earlier baseline only recorded a first-active observation at 23,758 ms; its old harness then waited for a manual-start condition that was not applicable. No completed exact baseline or calculated speedup is claimed.

## Show the completed engineering example

Use a 1440 × 900 desktop viewport for the reference layout.

1. Open [the earlier case]({source_link}). Select Process builder and inspect Compare both complete notices and its connection. Keep the original tenant and spouse documents available in the source rail.
2. Open [the receiving case]({target_link}) and choose Result checker. The actual historical Before/After comparison is visible immediately.
3. Show the receiving case's own 30. Juni and 31. Juli source passages. Selecting a source fact opens that case's original source.
4. Show the exact saved version 1 and its source/version provenance. Library version 2 does not silently replace the receiving case's existing pin.
5. Show the additional prerequisite and affected-step ordinal. Open the full-process disclosure when the complete 12-node graph is useful.
6. Show that Preserve challenge or extension deadline remains the next protective action and that the original evidence connection remains. Process validation is separate from approval of a claim outcome.

The [operator walkthrough](sealed-browser/review-walkthrough.webm) records the actual edit, preview, acceptance, saved version and later-case reuse from the completed release gate. Its Test handler events are engineering QA.

## Local workspace identities

- Standard workspace: http://127.0.0.1:4173/?journey=review&view=northstar
- Retained engineering example: http://127.0.0.1:4194/?journey=review&view=northstar
- Engineering session observed during verification: {engineering['current_server']['commander_session']}
- Standard session observed during verification: {standard['commander_running']['sessionId']}

The [engineering promotion receipt](release/engineering-promotion-verified-4864.json) identifies the current code, process, preserved previous-server bytes, original owner/copy receipts, and exact current data/view fingerprints. The [standard promotion receipt]({standard_path.relative_to(NS).as_posix()}) preserves the original data-root provenance and native boot lineage.

## Controlled future restart of the engineering example

Use the installed helpers on the owner's Mac. The copies in this bundle document the exact implementation; their install-path checks intentionally prevent executing them from the evidence directory.

Take a fresh checkpoint of the running owned service, stop only the session identified by that checkpoint, and preserve the actual Commander stop and terminal result objects. Use a new output filename and new session ID for each deliberate restart. Do not reuse an uncertain attempt or replay an application mutation.

~~~bash
CP_POLISH_ROOT='{ROOT}'
CP_POLISH_NS="$CP_POLISH_ROOT/.runtime/commander-demo-polish"
CP_POLISH_BASE="$CP_POLISH_NS/release"
CP_POLISH_PY="$CP_POLISH_ROOT/.runtime/casepath-dev-v2/venv/bin/python"

env PYTHONDONTWRITEBYTECODE=1 "$CP_POLISH_PY" -I -B \\
  "$CP_POLISH_BASE/verify_promoted_review_qa.py" checkpoint \\
  --out "$CP_POLISH_BASE/<fresh-before>.json"
~~~

After the parent has observed that exact owned session's actual terminal state, launch under a new owned Commander session. Use exec so the service PID equals the Commander PID:

~~~bash
exec env PYTHONDONTWRITEBYTECODE=1 "$CP_POLISH_PY" -I -B \\
  "$CP_POLISH_BASE/resume_promoted_review_qa.py" \\
  --before "$CP_POLISH_BASE/<fresh-before>.json" \\
  --stop-receipt "$CP_POLISH_BASE/<actual-stop>.json" \\
  --terminal-receipt "$CP_POLISH_BASE/<actual-terminal>.json" \\
  --session-id '<new-owned-session-id>'
~~~

Preserve the new actual running result, then verify once the service is ready:

~~~bash
env PYTHONDONTWRITEBYTECODE=1 "$CP_POLISH_PY" -I -B \\
  "$CP_POLISH_BASE/verify_promoted_review_qa.py" verify \\
  --before "$CP_POLISH_BASE/<fresh-before>.json" \\
  --running-receipt "$CP_POLISH_BASE/<actual-running>.json" \\
  --out "$CP_POLISH_BASE/<fresh-verification>.json"
~~~

These helpers preserve legitimate later QA edits. They do not copy, reset, seed, start or replay investigations. The original owner/copy evidence remains b206 ancestry; the running code uses the released immutable 4864 capsule.

## Standard workspace

The official launcher belongs to the original workspace at {OLD_ROOT}. It uses the existing separate standard data directory and native boot history. The completed source promotion was a fast-forward followed by official prepare; it was not a reset or data migration. Future starts use that workspace's official ./bin/casepath dev after its owned prior session has stopped and port 4173 is free. Preserve native boot history and DATA_ROOT_PROVENANCE.json. Do not rerun the one-time b206-to-4864 source-promotion attempt.

## Qualified review

Read [OPERATOR_REVIEW.md]({QUALIFIED_REVIEW}) for the source identities and remaining substantive judgment. The question is whether this additional notice-comparison prerequisite, its scope and completion criterion are appropriate for reuse while preserving protective actions and deadlines. Qualified approval remains pending; no engineering receipt substitutes for it.
"""
    return {"release-acceptance.json": json.dumps(release, indent=2) + "\n",
            "api-build-installation-excerpt.json": json.dumps(public["build_excerpt"], indent=2) + "\n",
            "baseline-preservation-summary.json": json.dumps(public["baseline_summary"], indent=2) + "\n",
            "README.md": readme, "demo-operator-guide.md": guide}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--standard-verified", type=Path, required=True)
    args = parser.parse_args()
    assert Path(__file__).resolve() == NS / "prepare_final_polish_evidence.py"
    assert sys.dont_write_bytecode and not BUNDLE.exists() and not (NS / "final-evidence-prepared.json").exists()
    binding = read(NS / "source-binding.json")
    assert binding["source_commit"] == SHA and binding["source_manifest_sha256"] == MANIFEST_SHA and binding["source_files"] == 1746
    engineering_before_import = read(BASE / "engineering-promotion-verified-4864.json")
    helper_path = BASE / "resume_promoted_review_qa.py"
    assert engineering_before_import["status"] == "passed"
    assert engineering_before_import["launcher_sha256"] == digest(helper_path)
    spec = importlib.util.spec_from_file_location("_polish_final_existing_release_checks", helper_path)
    assert spec is not None and spec.loader is not None
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    # This import-safe helper only validates release files/capsules here. Its
    # launcher main is never called, so no socket, app or database is opened.
    context = helper.release_context()
    gate = read(BASE / "full-gate-verified.json")
    plan = Plan()
    preseal = validate_preseal(plan, binding)
    sealed, _ = validate_adoption(plan, binding, gate)
    public = validate_public(plan)
    artifacts = validate_artifacts(plan, sealed)
    opening = validate_opening(plan)
    engineering = validate_engineering(plan, context["proof"], helper)
    standard = validate_standard(plan, args.standard_verified, context["proof"]["gate"])
    for name in (
        "source-binding.json", "seal-candidate.json", "sealed-candidate.patch", "prepare-candidate.json",
        "prepare-candidate.log", "full-gate-command.json", "full-gate.log",
    ):
        plan.add(NS / name)
    seal = read(NS / "seal-candidate.json")
    assert seal["status"] == "passed" and digest(NS / "seal-candidate.json") == binding["seal_sha256"]
    assert digest(NS / "sealed-candidate.patch") == binding["sealed_patch_sha256"]
    for stage in seal["stages"]:
        assert stage["status"] == "passed" and stage["exit_code"] == 0
        plan.add(stage["log"], expected=stage["log_sha256"], authority="seal-candidate.json")
    for name in ("full-gate-verified.json", "gate-actual-completion.json", "commander-terminal.json"):
        plan.add(BASE / name)
    plan.add(ROOT / "casepath/source-manifest.json", expected=MANIFEST_SHA, target="sealed-source-manifest.json")
    for name in RELEASE_HELPERS:
        plan.add(BASE / name)
    for name in NAMESPACE_HELPERS:
        plan.add(NS / name)
    # Optional transfer-helper source is safe; its archive/chunks are never copied.
    transfer_helper = BASE / "prepare_public_archive_transfer.py"
    if transfer_helper.exists():
        plan.add(transfer_helper)
    generated = reports(binding, gate, public, artifacts, opening, engineering, standard, args.standard_verified, preseal)
    assert not set(generated) & set(plan.copies)
    assert len([name for name in plan.copies if name.endswith(".webm")]) == 2
    assert len([name for name in plan.copies if re.fullmatch(r"release/public-film-review/cold-frame-[0-9]{2}\.png", name)]) == 24
    assert len([name for name in plan.copies if re.fullmatch(r"release/northstar-fidelity/concept-0[123]-(side|overlay|diff)\.png", name)]) == 9
    git = lambda *values: subprocess.check_output(
        ["/usr/bin/git", "--no-optional-locks", *values], cwd=ROOT, text=True, timeout=60).strip()
    assert git("rev-parse", "HEAD") == SHA and git("status", "--porcelain") == ""
    for row in plan.copies.values():
        assert digest(row["source_path"]) == row["original_sha256"], row["source_path"]
    # No partial bundle is advertised as prepared. A failed copy leaves this
    # fresh directory as evidence and cannot be silently overwritten on retry.
    BUNDLE.mkdir(mode=0o700)
    index = {"contract": "casepath.demo-polish-final-evidence/1", "tested_and_deployed_source": SHA,
             "source_manifest_sha256": MANIFEST_SHA, "generated_at": now(),
             "generator_sha256": digest(__file__), "intended_repository_destination": INTENDED_DESTINATION,
             "product_changes": False, "commit_or_push_performed": False,
             "qualified_human_approval": "pending", "copies": [], "derived": [],
             "validated_but_not_copied": plan.omitted,
             "excluded_payloads": ["private API seed", "full private collection readbacks", "full historical policy/budget history", "complete corpus",
                                   "credentials", "native boot base64 payloads", "raw public trace response bodies"],
             "preseal_development_pass_counts": preseal["development_pass_counts"]}
    for name, row in sorted(plan.copies.items()):
        target = BUNDLE / name
        target.parent.mkdir(parents=True, exist_ok=True)
        assert not target.exists()
        shutil.copyfile(row["source_path"], target, follow_symlinks=False)
        assert target.is_file() and not target.is_symlink()
        copied = digest(target)
        assert copied == row["original_sha256"] == digest(row["source_path"])
        assert target.stat().st_size == row["bytes"]
        index["copies"].append({**row, "copied_sha256": copied, "byte_identical": True})
    for name, text in generated.items():
        target = BUNDLE / name
        with target.open("x", encoding="utf-8") as stream:
            stream.write(text)
        index["derived"].append({"file": name, "sha256": digest(target), "bytes": target.stat().st_size,
                                 "basis": "Only validated actual input records; no additional test, review or deployment is claimed"})
    actual_files = {path.relative_to(BUNDLE).as_posix() for path in BUNDLE.rglob("*") if path.is_file()}
    assert actual_files == set(plan.copies) | set(generated), "Unexpected bundle content"
    assert git("rev-parse", "HEAD") == SHA and git("status", "--porcelain") == ""
    with (BUNDLE / "evidence-manifest.json").open("x") as stream:
        json.dump(index, stream, indent=2)
        stream.write("\n")
    result = {"source_commit": SHA, "status": "prepared", "bundle": str(BUNDLE),
              "files": len(actual_files) + 1, "copied_files": len(index["copies"]),
              "derived_files": len(index["derived"]), "manifest_sha256": digest(BUNDLE / "evidence-manifest.json"),
              "generator_sha256": digest(__file__), "source_clean_after": True,
              "product_changes": False, "commit_or_push_performed": False,
              "qualified_human_approval": "pending", "intended_repository_destination": INTENDED_DESTINATION}
    with (NS / "final-evidence-prepared.json").open("x") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
