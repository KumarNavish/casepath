#!/usr/bin/env python3
"""Package existing verified cinema evidence; never test, commit, push, or deploy.

Install under the cinema namespace. Invoke with --inputs <pack-inputs.json>.
The inputs file supplies actual final media/helper paths and saved Commander
terminal receipts. Validation precedes creation of a fresh ignored bundle.
"""
from __future__ import annotations

if not __debug__:
    raise RuntimeError("Assertions required")

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys

sys.dont_write_bytecode = True
ROOT = Path("/Users/kumar0002/Documents/Die Mobiliar/.work/casepath-commander-cinema-final-20261024")
NS = ROOT / ".runtime/cinema-release"
BASE = NS / "release"
_source_binding = json.loads((NS / "source-binding.json").read_text())
assert _source_binding["base_commit"] == "0ccf1eafcd27e0827e2d0778f9c2642e34cd05f9"
assert _source_binding["branch"] == "codex/casepath-cinema-final-20261024"
SHA = _source_binding["source_commit"]
TREE = _source_binding["source_tree"]
MANIFEST_SHA = _source_binding["source_manifest_sha256"]
assert re.fullmatch("[0-9a-f]{40}", SHA)
assert re.fullmatch("[0-9a-f]{40}", TREE)
assert re.fullmatch("[0-9a-f]{64}", MANIFEST_SHA)
DESTINATION = "design-plans/cinema-20261024/release-" + SHA[:8]
SITE = "https://casepath-autonomous.kumarnavish.chatgpt.site"
PROJECT = "appgprj_6ac8aab031988191b5c370f7a4dbf160"
BUNDLE = NS / "final-evidence-bundle"
READY = NS / "final-evidence-prepared.json"
ACTS = ["customer", "reading", "process", "decision", "learning", "cases"]
MEDIA_NAMES = {"01-source-video-probe", "02-source-score-probe", "03-loudnorm-pass1",
               "04-loudnorm-pass2", "05-mux", "06-output-probe",
               "07-original-video-packets", "08-output-video-packets",
               "09-full-decode", "10-final-aac-loudness"}


def regular(value):
    path = Path(value)
    assert path.is_absolute() and ".." not in path.parts, str(path)
    assert path.is_file() and not path.is_symlink(), str(path)
    for parent in path.parents:
        assert not parent.is_symlink(), str(parent)
        if parent == ROOT:
            break
    return path


def digest(value):
    path = regular(value)
    before = path.stat()
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    after = path.stat()
    assert (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) == (
        after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns), str(path)
    return result.hexdigest()


def read(value):
    return json.loads(regular(value).read_bytes())


def git(*args):
    return subprocess.check_output(
        ["/usr/bin/git", "--no-optional-locks", *args], cwd=ROOT,
        text=True, timeout=60).strip()


def source_clean():
    assert git("rev-parse", "HEAD") == SHA
    assert git("rev-parse", "HEAD^{tree}") == TREE
    assert git("status", "--porcelain") == ""
    assert digest(ROOT / "casepath/source-manifest.json") == MANIFEST_SHA


def safe_json(value):
    if isinstance(value, dict):
        assert not str(value.get("contract", "")).startswith("casepath.local-runtime-boot/")
        for key, child in value.items():
            normal = key.lower().replace("-", "_")
            assert normal not in {
                "authorization", "api_key", "access_token", "refresh_token",
                "client_secret", "password", "secret_value", "seed_base64",
                "payload_base64", "workspace_base64",
            }, "Secret-bearing field: " + key
            assert not (normal.endswith(("_base64", "_b64")) and isinstance(child, str)), key
            assert not (normal == "journal_rows" and isinstance(child, list)), "Raw journal"
            safe_json(child)
    elif isinstance(value, list):
        for child in value:
            safe_json(child)


class Plan:
    def __init__(self):
        self.files = {}
        self.omitted = []

    def add(self, source, target, expected=None):
        source = regular(source)
        assert source.is_relative_to(ROOT / ".runtime") or source == ROOT / "casepath/source-manifest.json"
        target_path = PurePosixPath(target)
        assert str(target_path) == target and not target_path.is_absolute() and ".." not in target_path.parts
        assert source.name not in {
            "readback-before.json", "readback-after.json", "baseline-binding.json",
            "api-build-log.json", "hosted-read-seed-v1.json",
        }
        assert not any(part in source.parts for part in ("inputs", "node_modules", "__pycache__"))
        assert not source.name.lower().endswith((".wav", ".aiff", ".flac", ".b64", ".sqlite3", ".db", ".tar.gz", ".zip"))
        actual = digest(source)
        if expected is not None:
            assert actual == expected, str(source)
        if source.suffix == ".json":
            safe_json(read(source))
        elif source.suffix == ".jsonl":
            for line in source.read_text().splitlines():
                if line.strip():
                    safe_json(json.loads(line))
        if source.suffix in {".json", ".jsonl", ".log", ".txt", ".py", ".cjs", ".mjs", ".patch"}:
            text = source.read_text()
            assert not re.search(r"Bearer\s+[A-Za-z0-9._~+/-]{24,}", text), str(source)
            assert not re.search(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----\s+[A-Za-z0-9/+]{20,}", text)
        row = {"file": target, "source_path": str(source), "sha256": actual, "bytes": source.stat().st_size}
        if target in self.files:
            assert self.files[target] == row
        else:
            self.files[target] = row

    def omit(self, source, expected, reason):
        source = regular(source)
        assert digest(source) == expected
        self.omitted.append({"source_path": str(source), "sha256": expected,
                             "bytes": source.stat().st_size, "copied": False, "reason": reason})


def terminal(plan, item, name):
    path = regular(item["path"])
    actual = read(path)
    assert actual["sessionId"] == item["session_id"]
    assert actual["state"] == "completed" and type(actual["exitCode"]) is int and actual["exitCode"] == 0
    plan.add(path, "terminals/" + name + ".json")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, required=True)
    args = parser.parse_args()
    source_clean()
    assert not BUNDLE.exists() and not READY.exists(), "Reconcile the original bundle; never overwrite it"
    inputs = read(args.inputs.resolve())
    assert inputs["source_commit"] == SHA
    binding = read(NS / "source-binding.json")
    assert binding["source_commit"] == SHA and binding["source_tree"] == TREE
    assert binding["source_manifest_sha256"] == MANIFEST_SHA and binding["source_files"] == 1746
    for relative, expected in binding["authored_sha256"].items():
        assert digest(ROOT / relative) == expected
    guard_path = NS / "require_completed_gate.py"
    spec = importlib.util.spec_from_file_location("_cinema_pack_completed_gate", guard_path)
    assert spec and spec.loader
    guard = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guard)
    assert guard.NS.resolve() == NS.resolve()
    guard.require_completed_gate(BASE, SHA)

    plan = Plan()
    plan.add(args.inputs.resolve(), "pack-inputs.json")
    for name in ["source-binding.json", "seal-candidate.json", "sealed-candidate.patch",
                 "prepare-candidate.json", "full-gate-command.json", "full-gate.log"]:
        plan.add(NS / name, name)
    for name in ["seal_candidate.py", "commit_prepare.py", "run_full_gate.py",
                 "require_completed_gate.py", "run_published_acceptance.py"]:
        plan.add(NS / name, "helpers/" + name)
    plan.add(regular(__file__), "helpers/prepare_evidence_bundle.py")
    plan.add(ROOT / "casepath/source-manifest.json", "sealed-source-manifest.json", MANIFEST_SHA)
    for field, target in [
        ("authored_files_input", "authored-files.json"),
        ("independent_review", "independent-review.json"),
        ("preseal_browser_receipt", "preseal/capture-receipt.json"),
    ]:
        item = binding[field]
        plan.add(item["path"], target, item["sha256"])
    review = read(binding["independent_review"]["path"])
    assert review["status"] == "passed" and review["blocking_findings"] == []

    # Recheck existing completed outcomes and artifact hashes, without reruns.
    acceptance = read(BASE / "published-acceptance-sequence.json")
    assert acceptance["source_commit"] == SHA and acceptance["status"] == "passed"
    assert [s["name"] for s in acceptance["stages"]] == ["soak", "browser", "image", "readback", "verify_readback"]
    for stage in acceptance["stages"]:
        assert stage["status"] == "completed" and stage["exit_code"] == 0
        plan.add(stage["log"], "release/" + Path(stage["log"]).name, stage["log_sha256"])
        for artifact in stage["artifacts"]:
            path = regular(artifact["path"])
            assert path.is_relative_to(BASE) and digest(path) == artifact["sha256"]
            if path.name == "readback-after.json":
                plan.omit(path, artifact["sha256"], "Full private collection readback retained in runtime")
            else:
                plan.add(path, "release/" + path.relative_to(BASE).as_posix(), artifact["sha256"])
    final = read(BASE / "readback-verified.json")
    assert final["canonical_commit"] == final["api_commit"] == final["frontend_commit"] == SHA
    assert all(final[k] is True for k in ["primary_reads_verified", "collection_unchanged", "knowledge_unchanged", "ledger_unchanged", "read_only"])
    assert final["writable"] is False and final["storage"] == "remote_primary"
    assert (final["claims"], final["provider_calls"], final["original_nine_workflows"], final["original_nine_calls"]) == (159, 42, 9, 18)
    api = read(BASE / "api-release-sequence.json")
    assert api["source_commit"] == SHA and api["status"] == "passed"
    saved, deployed, workflow = (read(BASE / name) for name in [
        "sites-saved-version.json", "sites-deployment.json", "sites-workflow-result.json"])
    assert saved["project_id"] == deployed["project_id"] == workflow["project_id"] == PROJECT
    assert deployed["version_id"] == saved["id"] and deployed["status"] == "succeeded" and deployed["url"] == SITE
    assert saved["source"]["commit_sha"] == workflow["commit_sha"]
    assert acceptance["site_version_id"] == saved["id"] and acceptance["distribution_commit"] == workflow["commit_sha"]
    soak = read(BASE / ("published-soak-" + SHA[:8]) / "summary.json")
    assert soak["source_commit"] == SHA and soak["passed"] is True
    assert soak["observed_soak_requests"] == soak["successful_soak_requests"] == 300
    assert soak["verification_requests"] == 7 and soak["runner_retries"] == soak["provider_calls_initiated"] == 0
    browser = read(BASE / ("published-browser-" + SHA[:8]) / "summary.json")
    assert [w["rendered"] for w in browser["windows"]] == [18, 9]
    assert all(w["commit_ok"] and w["rendered"] == w["total"] and not w["identity_failures"] and not w["errors"] and not w["writes"] and not w["overflow"] for w in browser["windows"])
    assert browser["film"]["reached_end"] and browser["film"]["duration_ms"] == 98550

    release_names = [
        "full-gate-verified.json", "gate-actual-completion.json", "commander-terminal.json",
        "canonical-integration.json", "seed-renewal-receipt.json", "api-environment-updated.json",
        "api-private-package-verified.json", "api-private-wheel-verified.json",
        "api-deployment-created.json", "api-deployment-uploaded.json", "api-health-after.json",
        "api-release-sequence.json", "sites-inputs-verified.json", "sites-workflow-result.json",
        "sites-saved-version.json", "sites-deployment.json", "published-acceptance-sequence.json",
        "readback-verified.json", "public-image-verified.json", "api-build-version.json",
        "helper-final-binding.json", "helper-acceptance-binding.json",
        "release-helper-adaptation.json", "presentation-expectation.json",
    ]
    for name in release_names:
        plan.add(BASE / name, "release/" + name)
    helper_binding = read(BASE / "helper-acceptance-binding.json")
    assert helper_binding["source_commit"] == SHA
    for name, expected in helper_binding["helpers"].items():
        plan.add(BASE / name, "release/" + name, expected)

    capture_path = regular(inputs["capture_receipt"])
    assert capture_path == ROOT / ".runtime/cinema-evidence/published-film/capture-receipt.json"
    capture = read(capture_path)
    assert capture["status"] == "passed" and capture["source_commit"] == SHA
    assert capture["browser_errors"] == capture["writes"] == capture["unexpected_destinations"] == []
    assert capture["new_inference"] is False and capture["mode"] == "deployed_read_only_replay"
    assert capture["health"]["source_commit"] == capture["deployment"]["source_commit"] == SHA
    assert capture["health"]["read_only"] is True and capture["health"]["writable"] is False
    for name, expected in capture["asset_sha256"].items():
        assert digest(ROOT / "casepath/assets" / name) == expected
    assert capture["timeline"]["duration"] == 98550 and [a["id"] for a in capture["timeline"]["acts"]] == ACTS
    assert capture["frame_count"] == 2957 and capture["fps"] == 30
    assert abs(capture["duration"] - 2957 / 30) < 1e-6
    assert capture["output"] == {"width": 1920, "height": 1080}
    timeline_path = capture_path.parent / "timeline.json"
    assert read(timeline_path) == capture["timeline"]
    frame_index = capture_path.parent / "frame-index.jsonl"
    assert digest(frame_index) == capture["frame_index_sha256"]
    rows = [json.loads(line) for line in frame_index.read_text().splitlines()]
    assert len(rows) == 2957
    assert all(row["n"] == i and abs(row["time"] - i * 1000 / 30) < 1e-6 and re.fullmatch("[0-9a-f]{64}", row["sha256"]) for i, row in enumerate(rows))
    silent = regular(capture_path.parent / capture["video"]["file"])
    assert silent.stat().st_size == capture["video"]["bytes"]
    assert digest(silent) == capture["video"]["sha256"]
    plan.add(capture_path, "film/capture-receipt.json")
    plan.add(timeline_path, "film/timeline.json")
    plan.add(frame_index, "film/frame-index.jsonl", capture["frame_index_sha256"])
    plan.add(silent, "film/CasePath_Cinematic_Demo_Silent.mp4", capture["video"]["sha256"])
    plan.add(capture_path.parent / "contact-sheet.png", "film/contact-sheet.png")
    assert len(capture["frames"]) == 24
    for ordinal in [1, 4, 7, 10, 14, 18, 21, 24]:
        row = capture["frames"][ordinal - 1]
        jpeg = regular(capture_path.parent / row["review_file"])
        assert jpeg.suffix == ".jpg"
        plan.add(jpeg, "film/selected-frames/" + jpeg.name)
    if (capture_path.parent / "encode.log").exists():
        plan.add(capture_path.parent / "encode.log", "film/encode.log")

    media_path = regular(inputs["media_receipt"])
    media = read(media_path)
    assert media["passed"] is True and media["originals_unchanged"] is True and media["video_reencoding"] is False
    assert Path(media["silent"]) == silent and media["input_sha256"]["silent"] == capture["video"]["sha256"]
    movie = regular(media["output"])
    assert movie.suffix == ".mp4" and digest(movie) == media["output_sha256"]
    assert movie.stat().st_size == media["output_bytes"]
    assert media["video_frames"] == 2957 and media["audio_pcm_samples"] == 4731200
    assert abs(media["duration_seconds"] - 2957 / 30) < 1e-6
    assert media["encoded_video_sha256"]["source"] == media["encoded_video_sha256"]["output"]
    assert math.isfinite(media["measured_integrated_lufs"]) and abs(media["measured_integrated_lufs"] + 20) <= .5
    assert math.isfinite(media["measured_true_peak_dbtp"]) and media["measured_true_peak_dbtp"] <= -2
    assert MEDIA_NAMES <= {row["name"] for row in media["commands"]}
    assert all(row["exit_code"] == 0 for row in media["commands"])
    score_path = regular(media["score"])
    score_receipt = score_path.with_suffix(".score.json")
    score = read(score_receipt)
    assert score["recordings_used"] is False and score["network_used"] is False and score["model_or_provider_calls"] is False
    score_timeline_path = regular(score["timeline_file"])
    assert digest(score_timeline_path) == score["timeline_sha256"]
    score_timeline = read(score_timeline_path)
    for key in ("timeline", "manifest"):
        if isinstance(score_timeline, dict) and isinstance(score_timeline.get(key), dict):
            score_timeline = score_timeline[key]
            break
    # The score may have been rendered before publication. Its actual input
    # timeline and second-based cue boundaries must match the final public film.
    assert score_timeline["duration"] == capture["timeline"]["duration"]
    assert score_timeline["acts"] == capture["timeline"]["acts"]
    expected_score_acts = [{"id": str(act["id"]), "start": act["start"] / 1000.0,
                           "end": act["end"] / 1000.0} for act in capture["timeline"]["acts"]]
    assert score["acts"] == expected_score_acts
    assert abs(score["duration_seconds"] - media["duration_seconds"]) <= 1 / score["sample_rate"] + 1e-8
    assert Path(score["output_file"]) == score_path
    assert score["output_sha256"] == media["input_sha256"]["score"] == digest(score_path)
    plan.add(movie, "film/CasePath_Cinematic_Demo.mp4", media["output_sha256"])
    plan.add(media_path, "film/media-receipt.json")
    plan.add(score_receipt, "film/score-receipt.json")
    plan.add(score_timeline_path, "film/score-timeline-input.json", score["timeline_sha256"])
    plan.omit(score_path, score["output_sha256"], "Reproducible original PCM score; final AAC is included in the scored film")
    evidence = movie.parent / (movie.stem + "-media-evidence")
    for command in media["commands"]:
        assert re.fullmatch(r"[0-9]{2}-[a-z0-9-]+", command["name"])
        for suffix in [".stdout.txt", ".stderr.txt"]:
            path = evidence / (command["name"] + suffix)
            plan.add(path, "film/media-evidence/" + path.name)
    if (evidence / "loudness-pass1.json").exists():
        plan.add(evidence / "loudness-pass1.json", "film/media-evidence/loudness-pass1.json")
    for key, target in [("capture_helper", "capture.cjs"), ("score_helper", "score.py"), ("mux_helper", "master_and_mux.py")]:
        plan.add(inputs[key], "film/helpers/" + target)
    assert set(inputs["terminals"]) == {"acceptance", "capture", "media"}
    for name, item in inputs["terminals"].items():
        terminal(plan, item, name)

    fidelity_dir = ROOT / ".runtime/cinema-evidence/fidelity-final"
    fidelity_path = fidelity_dir / "fidelity-receipt.json"
    fidelity = read(fidelity_path)
    assert fidelity["source_commit"] == SHA and fidelity["status"] == "passed"
    for name, expected in fidelity["source_assets"].items():
        assert digest(ROOT / "casepath/assets" / name) == expected
    assert len(fidelity["comparisons"]) == 3
    assert digest(ROOT / "design-plans/tools/fidelity.mjs") == fidelity["tool_sha256"]
    plan.add(fidelity_path, "fidelity/fidelity-receipt.json")
    plan.add(fidelity_dir / "receipt.json", "fidelity/capture-receipt.json")
    for number, row in enumerate(fidelity["comparisons"], 1):
        assert digest(ROOT / row["concept"]) == row["concept_sha256"]
        assert digest(row["frame"]) == row["frame_sha256"]
        assert math.isfinite(row["mean_difference_pct"]) and 0 <= row["mean_difference_pct"] <= 100
        for kind in ["side", "overlay", "diff"]:
            image = fidelity_dir / f"concept-{number}-{kind}.png"
            plan.add(image, "fidelity/" + image.name)

    # Optional small authored review records are explicit, never a tree copy.
    for item in inputs.get("review_records", []):
        assert Path(item["path"]).suffix in {".json", ".md"}
        plan.add(item["path"], "reviews/" + Path(item["path"]).name, item["sha256"])
    guard.require_completed_gate(BASE, SHA)
    source_clean()
    summary = {
        "contract": "casepath.cinema-release-acceptance/1", "tested_and_deployed_source": SHA,
        "source_tree": TREE, "source_manifest_sha256": MANIFEST_SHA,
        "site_url": SITE, "site_version_id": saved["id"], "site_version_number": saved["version_number"],
        "site_deployment_id": deployed["id"], "distribution_commit": workflow["commit_sha"],
        "public_acceptance_sha256": digest(BASE / "published-acceptance-sequence.json"),
        "gate_actual_completion_sha256": digest(BASE / "gate-actual-completion.json"),
        "provider_calls_total": final["provider_calls"], "new_provider_workflows_started": 0,
        "collection_unchanged": True, "knowledge_unchanged": True, "ledger_unchanged": True,
        "product_duration_ms": 98550, "encoded_duration_seconds": media["duration_seconds"],
        "video_frames": 2957, "film_capture_mode": capture["mode"],
        "silent_sha256": capture["video"]["sha256"], "scored_sha256": media["output_sha256"],
        "audio_integrated_lufs": media["measured_integrated_lufs"], "audio_true_peak_dbtp": media["measured_true_peak_dbtp"],
        "audio_subjective_listening_claimed": False, "qualified_human_approval": "not_claimed",
        "intended_repository_destination": DESTINATION, "product_changes": False,
        "commit_or_push_performed": False,
    }
    readme = f"""# CasePath cinematic demonstration

Tested and deployed product source: {SHA}.

[Watch with the original score](film/CasePath_Cinematic_Demo.mp4) · [Watch silently](film/CasePath_Cinematic_Demo_Silent.mp4) · [Open the live presentation]({SITE}/?present=1#autonomous/demonstration)

The product presentation is 98.55 seconds. The exported film has 2,957 frames at 30 fps (98.5666667 seconds), with the same H.264 video packets in the silent and scored versions. The score is original deterministic synthesis. The final audio was measured and decoded; no subjective listening is claimed.

The six chapters connect the customer question, exact evidence, process, assessment, next-case checklist reuse, and closing message. These are recorded fictional examples. Human review remains required.

The release acceptance summary contains only validated existing receipts. The evidence manifest identifies exact copied bytes and intentionally omitted payloads. Public acceptance retains the complete release gate, 300 sequential read checks, 18 desktop and 9 mobile case views, exact asset checks, continuous public playback, and unchanged data/provider-ledger checks.

The fidelity comparisons use unchanged concepts and final 1440×900 product views. Pixel difference percentages are measurements, not perceptual quality scores.

Private seed bytes, raw collection readbacks, credentials, full frame PNG directories, intermediate PCM masters, and listening-preview WAVs are excluded. The score recipe, timeline, rendering helpers, and small media logs are included.

This package does not change product code. The sealed product checkout remains clean at the product commit. A later evidence-only commit records this directory without changing the deployed source identity.
"""
    generated = {"release-acceptance.json": json.dumps(summary, indent=2) + "\n", "README.md": readme}
    assert not set(generated) & set(plan.files)
    BUNDLE.mkdir(mode=0o700)
    for name, row in sorted(plan.files.items()):
        target = BUNDLE / name
        target.parent.mkdir(parents=True, exist_ok=True)
        assert digest(row["source_path"]) == row["sha256"]
        shutil.copyfile(row["source_path"], target, follow_symlinks=False)
        assert digest(target) == row["sha256"] == digest(row["source_path"])
    for name, text in generated.items():
        with (BUNDLE / name).open("x") as stream:
            stream.write(text)
    source_clean()
    actual = {p.relative_to(BUNDLE).as_posix() for p in BUNDLE.rglob("*") if p.is_file()}
    assert actual == set(plan.files) | set(generated)
    manifest = {
        "contract": "casepath.cinema-evidence-manifest/1", "source_commit": SHA,
        "created_at": datetime.now(timezone.utc).isoformat(), "generator_sha256": digest(__file__),
        "intended_repository_destination": DESTINATION, "product_changes": False,
        "commit_or_push_performed": False, "copies": list(plan.files.values()),
        "derived": [{"file": name, "sha256": digest(BUNDLE / name), "bytes": (BUNDLE / name).stat().st_size} for name in generated],
        "validated_but_not_copied": plan.omitted,
        "excluded": ["private seed bytes", "credentials", "raw collection readbacks", "large frame PNG directories", "intermediate audio"],
    }
    with (BUNDLE / "evidence-manifest.json").open("x") as stream:
        json.dump(manifest, stream, indent=2)
        stream.write("\n")
    result = {"source_commit": SHA, "status": "prepared", "bundle": str(BUNDLE),
              "files": len(actual) + 1, "manifest_sha256": digest(BUNDLE / "evidence-manifest.json"),
              "source_clean_after": True, "product_changes": False, "commit_or_push_performed": False,
              "intended_repository_destination": DESTINATION}
    with READY.open("x") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
