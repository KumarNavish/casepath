#!/usr/bin/env python3
"""Pack verified narration, then optionally commit/push its separate supplement.

No rendering, providers, deployment, source edits, or automatic retries. Run
`pack` only with actual successful receipts. `commit` requires an explicit
expected canonical HEAD after the strict evidence has already been committed.
Both commands preserve the isolated product checkout at SOURCE.
"""
from __future__ import annotations

if not __debug__:
    raise RuntimeError("Assertions must remain enabled; do not use Python -O")

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import signal
import subprocess
import sys

sys.dont_write_bytecode = True
SOURCE = "a1b59cf5d78662b35790a11cfd2d46851310482d"
BASE_SOURCE = "5da3233a0aa04ad29843c8ec55dfb685118381c9"
ROOT = Path("/Users/kumar0002/Documents/Die Mobiliar/.work/casepath-commander-documentary-20261024")
SOURCE_BRANCH = "codex/casepath-documentary-20261025"
CANONICAL = ROOT.parent / "casepath-sites-hosting-20261009"
CANONICAL_BRANCH = "codex/casepath-causal-experience-integration-20261009"
REFERENCE = "refs/heads/" + CANONICAL_BRANCH
NS = ROOT / ".runtime/documentary-release-20261025"
RUNTIME = ROOT / ".runtime/cinema-evidence/audio-20261025" / ("supplement-" + SOURCE[:8])
BUNDLE = RUNTIME / "bundle"
READY = RUNTIME / "narration-evidence-prepared.json"
PACK_ATTEMPT = RUNTIME / "pack-attempt.json"
COMMIT_ATTEMPT = RUNTIME / "commit-attempt.json"
LOGS = RUNTIME / "commit-commands"
DESTINATION = "design-plans/documentary-20261025/narration-" + SOURCE[:8]
WORKTREE = ROOT.parent / ("casepath-documentary-narration-evidence-" + SOURCE[:8])
EVIDENCE_BRANCH = "codex/casepath-documentary-narration-evidence-" + SOURCE[:8]
GIT = "/usr/bin/git"
SAY = "/usr/bin/say"
FFMPEG = "/Users/kumar0002/.local/bin/ffmpeg"
FFPROBE = "/Users/kumar0002/.local/bin/ffprobe"
FRAMES, FPS, RATE = 2957, 30, 48000
SAMPLES = FRAMES * (RATE // FPS)
DURATION = FRAMES / FPS
ALLOWED_REMOTES = {
    "https://github.com/KumarNavish/casepath.git",
    "git@github.com:KumarNavish/casepath.git",
}
ENV = {key: os.environ[key] for key in (
    "PATH", "HOME", "USER", "LOGNAME", "LANG", "LC_ALL", "TZ", "SSH_AUTH_SOCK",
) if key in os.environ}
ENV.update(GIT_TERMINAL_PROMPT="0", PYTHONDONTWRITEBYTECODE="1")
ENV.setdefault("PATH", "/usr/bin:/bin:/usr/sbin:/sbin:/usr/local/bin")
HASH = re.compile(r"[0-9a-f]{64}\Z")
COMMIT = re.compile(r"[0-9a-f]{40}\Z")
SECRET_FIELDS = {
    "authorization", "api_key", "access_token", "refresh_token", "client_secret",
    "password", "secret_value", "seed_base64", "payload_base64", "workspace_base64",
}
PRIVATE_FILENAMES = {
    "readback-before.json", "readback-after.json", "baseline-binding.json",
    "api-build-log.json", "hosted-read-seed-v1.json",
}
PROOF_COMMANDS = {
    "installed-voices", "source-video-probe", "narrated-film-probe",
    "source-video-packets", "narrated-video-packets", "full-narrated-decode",
    "final-aac-loudness", "voice-window-verification",
}


def now():
    return datetime.now(timezone.utc).isoformat()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def regular(value, *, runtime=True):
    path = Path(value)
    require(path.is_absolute() and ".." not in path.parts, "An absolute, non-traversing path is required")
    if runtime:
        require(path.is_relative_to(ROOT / ".runtime"), "Input must be inside the isolated runtime: " + str(path))
    require(path.is_file() and not path.is_symlink(), "Not a regular input: " + str(path))
    for parent in path.parents:
        require(not parent.is_symlink(), "Symlink ancestor: " + str(parent))
    return path


def digest(value, *, runtime=True):
    path = regular(value, runtime=runtime)
    before = path.stat()
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    after = path.stat()
    require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) ==
            (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns), "Input changed during read: " + str(path))
    return value.hexdigest()


def read(value):
    return json.loads(regular(value).read_bytes())


def hashed_file(row):
    require(isinstance(row, dict) and set(row) == {"path", "sha256"}, "Expected an exact path/SHA descriptor")
    require(isinstance(row["sha256"], str) and HASH.fullmatch(row["sha256"]), "Invalid SHA-256")
    path = regular(row["path"])
    require(digest(path) == row["sha256"], "Input hash mismatch: " + str(path))
    return path


def safe_relative(name):
    require(isinstance(name, str) and "\\" not in name, "Invalid relative name")
    path = PurePosixPath(name)
    require(name == str(path) and name not in {"", "."} and not path.is_absolute()
            and ".." not in path.parts and ".git" not in path.parts, "Unsafe relative name: " + name)
    return name


def safe_json(value):
    if isinstance(value, dict):
        require(not str(value.get("contract", "")).startswith("casepath.local-runtime-boot/"), "Private runtime input is excluded")
        for key, child in value.items():
            normal = key.lower().replace("-", "_")
            require(normal not in SECRET_FIELDS, "Secret-bearing field is excluded: " + key)
            require(not (normal.endswith(("_base64", "_b64")) and isinstance(child, str)), "Encoded payload is excluded: " + key)
            require(not (normal == "journal_rows" and isinstance(child, list)), "Raw journal is excluded")
            safe_json(child)
    elif isinstance(value, list):
        for child in value:
            safe_json(child)


def safe_text(text):
    require(not re.search(r"Bearer\s+[A-Za-z0-9._~+/-]{24,}", text), "Credential text is excluded")
    require(not re.search(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----\s+[A-Za-z0-9/+]{20,}", text), "Private key is excluded")
    require(not re.search(r"(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{30,})", text), "GitHub credential is excluded")


def new_json(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def persist(path, value, *, first=False):
    temporary = path if first else path.with_suffix(".next")
    new_json(temporary, value)
    if not first:
        os.replace(temporary, path)


def git_result(cwd, *args):
    return subprocess.run([GIT, "--no-optional-locks", *args], cwd=cwd, env=ENV,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)


def git_bytes(cwd, *args):
    result = git_result(cwd, *args)
    require(result.returncode == 0, "Git read failed: " + repr(args) + ": " + result.stderr.decode(errors="replace")[-1500:])
    return result.stdout


def git(cwd, *args):
    return git_bytes(cwd, *args).decode().strip()


def paths(raw):
    return [name.decode("utf-8") for name in raw.split(b"\0") if name]


def source_clean(binding=None):
    binding_path = NS / "source-binding.json"
    binding = read(binding_path) if binding is None else binding
    require(binding["source_commit"] == SOURCE and binding["base_commit"] == BASE_SOURCE
            and binding["branch"] == SOURCE_BRANCH, "Wrong source binding")
    require(COMMIT.fullmatch(binding["source_tree"]) and HASH.fullmatch(binding["source_manifest_sha256"]), "Malformed source binding")
    require(git(ROOT, "branch", "--show-current") == SOURCE_BRANCH, "Isolated source branch changed")
    require(git(ROOT, "rev-parse", "HEAD") == SOURCE, "Isolated source HEAD changed")
    require(git(ROOT, "rev-parse", "HEAD^{tree}") == binding["source_tree"], "Isolated source tree changed")
    require(git(ROOT, "status", "--porcelain", "--untracked-files=all") == "", "Isolated product checkout must be clean")
    require(digest(ROOT / "casepath/source-manifest.json", runtime=False) == binding["source_manifest_sha256"], "Source manifest changed")
    return binding


def exact_files(folder, expected):
    require(folder.is_dir() and not folder.is_symlink(), "Bundle directory is missing or linked")
    actual = set()
    for path in folder.rglob("*"):
        require(not path.is_symlink() and (path.is_file() or path.is_dir()), "Unsupported bundle entry: " + str(path))
        if path.is_file():
            actual.add(path.relative_to(folder).as_posix())
    require(actual == set(expected), "Bundle file inventory differs from its manifest")
    for name, row in expected.items():
        safe_relative(name)
        path = regular(folder / name, runtime=False)
        require(path.stat().st_size == row["bytes"] and digest(path, runtime=False) == row["sha256"], "Bundle bytes differ: " + name)


def manifest_files(manifest, manifest_path, *, key_sets=("copies", "derived")):
    result = {}
    for key in key_sets:
        for row in manifest[key]:
            name = safe_relative(row["file"])
            require(name not in result and HASH.fullmatch(row["sha256"]) and type(row["bytes"]) is int and row["bytes"] >= 0,
                    "Malformed or duplicate manifest entry")
            result[name] = {"sha256": row["sha256"], "bytes": row["bytes"]}
    require(manifest_path.name not in result, "A manifest must not pretend to hash itself")
    result[manifest_path.name] = {"sha256": digest(manifest_path), "bytes": manifest_path.stat().st_size}
    return result


def strict_evidence(path, binding):
    require(path == NS / "final-evidence-prepared.json", "Use the actual strict final-evidence-prepared receipt")
    ready = read(path)
    require(ready["status"] == "prepared" and ready["source_commit"] == SOURCE, "Strict evidence is not prepared for this source")
    require(ready["source_clean_after"] is True and ready["product_changes"] is False
            and ready["commit_or_push_performed"] is False, "Unexpected strict preparation state")
    folder = Path(ready["bundle"])
    require(folder == NS / "final-evidence-bundle", "Unexpected strict bundle location")
    destination = safe_relative(ready["intended_repository_destination"])
    require(destination == "design-plans/documentary-20261025/release-" + SOURCE[:8], "Unexpected strict repository destination")
    manifest_path = regular(folder / "evidence-manifest.json")
    require(digest(manifest_path) == ready["manifest_sha256"], "Strict manifest hash mismatch")
    manifest = read(manifest_path)
    require(manifest["contract"] == "casepath.cinema-evidence-manifest/1"
            and manifest["source_commit"] == SOURCE and manifest["intended_repository_destination"] == destination,
            "Strict manifest source or destination mismatch")
    require(manifest["product_changes"] is False and manifest["commit_or_push_performed"] is False, "Unexpected strict manifest state")
    expected = manifest_files(manifest, manifest_path)
    require(ready["files"] == len(expected), "Strict file count mismatch")
    exact_files(folder, expected)
    acceptance = read(folder / "release-acceptance.json")
    require(acceptance["tested_and_deployed_source"] == SOURCE
            and acceptance["source_tree"] == binding["source_tree"]
            and acceptance["source_manifest_sha256"] == binding["source_manifest_sha256"], "Strict acceptance source mismatch")
    require(acceptance["video_frames"] == FRAMES and acceptance["product_duration_ms"] == 98550, "Unexpected strict film")
    require(all(acceptance[key] is True for key in ("collection_unchanged", "knowledge_unchanged", "ledger_unchanged")), "Strict acceptance did not preserve state")
    require(acceptance["new_provider_workflows_started"] == 0 and acceptance["product_changes"] is False, "Unexpected strict release action")
    require(digest(folder / "sealed-source-manifest.json") == binding["source_manifest_sha256"], "Strict sealed manifest mismatch")
    return {"ready": ready, "manifest": manifest, "expected": expected,
            "folder": folder, "destination": destination, "acceptance": acceptance}


def terminal_result(path, session_id):
    require(re.fullmatch(r"[A-Za-z0-9_.:-]{1,200}", session_id), "An exact Commander session ID is required")
    terminal = read(path)
    require(isinstance(terminal, dict) and terminal.get("sessionId") == session_id, "Wrong Commander session")
    require(terminal.get("state") == "completed" and type(terminal.get("exitCode")) is int
            and terminal["exitCode"] == 0, "Commander did not report successful completion")
    require(type(terminal.get("pid")) is int and terminal["pid"] > 0 and terminal.get("startedAt")
            and terminal.get("finishedAt") and isinstance(terminal.get("output"), str), "Not an actual saved Commander process result")
    safe_json(terminal)
    safe_text(json.dumps(terminal))
    return terminal


def anchor_time(timeline, anchor):
    beats = [beat for beat in timeline["beats"] if beat["act"] == anchor["act"] and beat["phase"] == anchor["phase"]]
    index = anchor["occurrence"]
    require(beats and type(index) is int and (index == -1 or 0 <= index < len(beats)), "Missing narration phase anchor")
    require(anchor["edge"] in {"start", "end"} and type(anchor["offset_ms"]) is int, "Invalid narration anchor")
    return beats[index][anchor["edge"]] + anchor["offset_ms"]


def focus_window(timeline, selector, mode):
    require(isinstance(selector, dict) and set(selector) <= {"id", "target", "target_id"}
            and isinstance(selector.get("id"), str) and selector["id"], "Invalid semantic focus selector")
    require(mode in {"spotlight", "chapter-framing"}, "Invalid narration focus mode")
    rows = [row for row in timeline["guidance"] if row.get("id") == selector["id"]
            and ("target" not in selector or row.get("target") == selector["target"])
            and ("target_id" not in selector or row.get("targetId") == selector["target_id"])]
    require(rows, "No matching narration focus")
    if mode == "spotlight":
        require(all(row.get("spotlight") is True for row in rows), "Narration cue has no spotlight")
    else:
        require(selector["id"] in {"question", "finale"}, "Only introduction and finale use chapter framing")
    rows.sort(key=lambda row: row["start"])
    start = end = rows[0]["start"]
    for row in rows:
        require(type(row["start"]) is int and type(row["end"]) is int
                and 0 <= row["start"] < row["end"] <= timeline["duration"]
                and row["start"] == end, "Narration focus is ambiguous or discontinuous")
        end = row["end"]
    visible_start = start
    transitions = [] if mode == "chapter-framing" else sorted(
        (beat for beat in timeline["beats"] if beat["phase"] in {"act-transition", "scene-transition"}
         and beat["start"] < end and beat["end"] > start), key=lambda beat: beat["start"])
    for beat in transitions:
        require(beat["start"] <= visible_start, "Narration focus is interrupted by a hidden transition")
        visible_start = max(visible_start, beat["end"])
    require(visible_start < end, "Narration focus never becomes visible")
    return {"selector": selector, "mode": mode, "guidance_start_ms": start,
            "start_ms": visible_start, "end_ms": end, "guidance_segments": len(rows),
            "excluded_entering_transition_ms": visible_start - start,
            "settle_reference": "chapter-cue-start" if mode == "chapter-framing" else "visible-spotlight-arrival"}


def validate_srt(path, cues):
    text = regular(path).read_text(encoding="utf-8")
    safe_text(text)
    blocks = re.split(r"\n\s*\n", text.strip())
    require(len(blocks) == len(cues), "SRT cue count differs from actual narration")

    def millis(stamp):
        match = re.fullmatch(r"(\d{2}):(\d{2}):(\d{2}),(\d{3})", stamp)
        require(match, "Invalid SRT timestamp")
        hours, minutes, seconds, milliseconds = map(int, match.groups())
        require(minutes < 60 and seconds < 60, "Invalid SRT time")
        return ((hours * 60 + minutes) * 60 + seconds) * 1000 + milliseconds

    previous_end = 0
    for index, (block, cue) in enumerate(zip(blocks, cues), 1):
        lines = block.splitlines()
        require(len(lines) >= 3 and lines[0] == str(index), "Invalid SRT sequence")
        timing = lines[1].split(" --> ")
        require(len(timing) == 2, "Invalid SRT time range")
        start, end = map(millis, timing)
        require(start == round(cue["start_ms"]) and end == round(cue["actual_end_ms"])
                and previous_end <= start < end <= math.ceil(DURATION * 1000), "SRT timing differs from the measured clips")
        require(" ".join(" ".join(lines[2:]).split()) == " ".join(cue["selected"]["text"].split()), "SRT wording differs from the actual selected narration")
        previous_end = end


def finite(value):
    require(not isinstance(value, bool) and math.isfinite(float(value)), "Non-finite measurement")
    return float(value)


def video_probe(probe, *, final):
    streams = probe["streams"]
    videos = [row for row in streams if row["codec_type"] == "video"]
    audios = [row for row in streams if row["codec_type"] == "audio"]
    require(len(videos) == 1 and len(streams) == (2 if final else 1) and len(audios) == (1 if final else 0), "Unexpected film streams")
    video = videos[0]
    require(video["codec_name"] == "h264" and video["avg_frame_rate"] == "30/1"
            and (video["width"], video["height"]) == (1920, 1080), "Film is not 1080p30 H.264")
    require(int(video["nb_frames"]) == FRAMES and abs(finite(video["duration"]) - DURATION) < 1e-5, "Unexpected film frame count or duration")
    if final:
        require(int(video["nb_read_frames"]) == FRAMES, "Full video frame count was not verified")
        audio = audios[0]
        require(audio["codec_name"] == "aac" and int(audio["sample_rate"]) == RATE and int(audio["channels"]) == 2, "Unexpected final audio encoding")
        require(abs(finite(audio.get("start_time", 0))) <= 1 / RATE + 1e-6, "Unexpected audio start offset")
        require(abs(finite(audio["duration"]) - DURATION) <= 1024 / RATE + .001, "Unexpected audio duration")


def narration_evidence(receipt_path, binding, strict):
    report = read(receipt_path)
    require(receipt_path.name == "narration-receipt.json" and receipt_path.parent.is_relative_to(ROOT / ".runtime/cinema-evidence/audio-20261025"), "Unexpected narration receipt location")
    out = receipt_path.parent
    require(report["contract"] == "casepath.documentary-narration/1" and report["status"] == "passed"
            and report["passed"] is True and report["source_commit"] == SOURCE, "Narration did not pass for this source")
    require(report["originals_unchanged"] is True and report["video_reencoding"] is False, "Narration modified original media")
    require(all(report[key] is False for key in ("network_commands", "provider_or_model_calls", "voice_downloads", "subjective_listening_claimed")), "Unexpected narration provenance")
    require(report["video_frames"] == FRAMES and report["audio_pcm_samples"] == SAMPLES
            and abs(finite(report["duration_seconds"]) - DURATION) < 1e-6, "Unexpected narration length")
    require(Path(report["source_binding"]["path"]) == NS / "source-binding.json"
            and report["source_binding"]["sha256"] == digest(NS / "source-binding.json"), "Narration source binding changed")
    voice = report["voice"]
    require((voice["name"], voice["language"], voice["engine"]) == ("Daniel", "en-GB", SAY)
            and voice["speed_range_wpm"] == [145, 180]
            and re.match(r"^Daniel\s+en_GB\s", voice["installed_inventory_line"]), "Offline installed Daniel voice was not established")
    paths_by_name = {name: hashed_file(row) for name, row in report["input_files"].items()}
    require(set(paths_by_name) == {"silent_video", "score_master", "capture_receipt", "media_receipt", "timeline", "plan"}, "Unexpected narration input set")
    inputs_path = regular(out / "input-bindings.json")
    require(digest(inputs_path) == report["inputs_sha256"], "Narration input bindings changed")
    inputs = read(inputs_path)
    require(inputs["contract"] == "casepath.documentary-narration-inputs/1" and inputs["source_commit"] == SOURCE
            and Path(inputs["out_dir"]) == out and inputs["files"] == report["input_files"], "Narration inputs disagree")
    plan = read(paths_by_name["plan"])
    require(plan["contract"] == "casepath.documentary-narration-plan/1" and plan["voice"] == "Daniel"
            and plan["language"] == "en-GB" and plan["engine"] == SAY, "Unexpected narration plan")
    require(plan["provider_or_model_calls"] is False and plan["downloads"] is False, "Plan permits external narration")
    require(plan["planned_duration_ms"] == 98550 and plan["fps"] == FPS and plan["max_words"] == 110
            and plan["reviewed_cue_count"] == report["reviewed_cue_count"] == 17
            and report["max_words"] == plan["max_words"], "Unexpected narration scope")
    require(report["focus_policy"] == {"minimum_settle_ms": plan["minimum_focus_settle_ms"],
            "exit_guard_ms": plan["focus_exit_guard_ms"], "entering_transitions_excluded": True,
            "spotlight_clips": 15, "chapter_framing_clips": 2, "all_windows_within_matching_cue": True}
            and plan["exclude_entering_transitions"] is True
            and 300 <= plan["minimum_focus_settle_ms"] <= 1000
            and 0 <= plan["focus_exit_guard_ms"] <= 500, "Narration focus policy mismatch")
    require((plan["min_rate_wpm"], plan["max_rate_wpm"]) == (145, 180)
            and 145 <= plan["preferred_rate_wpm"] <= 180, "Unexpected speech rate")
    timeline, capture, media = (read(paths_by_name[name]) for name in ("timeline", "capture_receipt", "media_receipt"))
    require(timeline == capture["timeline"] and timeline["duration"] == 98550, "Narration timeline mismatch")
    require(capture["status"] == "passed" and capture["source_commit"] == SOURCE
            and capture["mode"] == "deployed_read_only_replay" and capture["new_inference"] is False, "Narration did not use the passed public capture")
    require(capture["health"]["source_commit"] == capture["deployment"]["source_commit"] == SOURCE
            and capture["health"]["read_only"] is True and capture["health"]["writable"] is False, "Public capture identity mismatch")
    require(capture["browser_errors"] == capture["writes"] == capture["unexpected_destinations"] == [], "Public capture has failures or writes")
    require(capture["fps"] == FPS and capture["frame_count"] == FRAMES, "Unexpected captured frame count")
    require(capture["video"]["sha256"] == report["input_files"]["silent_video"]["sha256"] == strict["acceptance"]["silent_sha256"], "Strict and narrated films use different source video")
    require(paths_by_name["capture_receipt"].parent / capture["video"]["file"] == paths_by_name["silent_video"], "Capture path mismatch")
    require(media["passed"] is True and media["originals_unchanged"] is True and media["video_reencoding"] is False, "Original score mastering did not pass")
    require(Path(media["silent"]) == paths_by_name["silent_video"]
            and media["input_sha256"]["silent"] == capture["video"]["sha256"]
            and media["pcm_master_sha256"] == report["input_files"]["score_master"]["sha256"], "Original score inputs changed")
    require(media["video_frames"] == FRAMES and media["audio_pcm_samples"] == SAMPLES, "Original score length mismatch")
    scored = hashed_file(report["existing_scored_film"])
    require(scored == Path(media["output"]) and report["existing_scored_film"]["sha256"] == media["output_sha256"] == strict["acceptance"]["scored_sha256"], "Strict scored film mismatch")
    film = regular(report["output"])
    require(film == out / "CasePath_Documentary_Narrated.mp4" and digest(film) == report["output_sha256"]
            and film.stat().st_size == report["output_bytes"], "Narrated film bytes changed")
    require(digest(out / "narration-plan.json") == report["input_files"]["plan"]["sha256"], "Copied narration plan changed")
    helper = regular(report["helper_path"])
    require(digest(helper) == report["helper_sha256"] == digest(out / "render_documentary_narration.py"), "Narration helper changed")
    require(read(out / "cue-timings.json") == report["cues"], "Cue timings disagree with the successful receipt")
    require(len(report["cues"]) == len(plan["cues"]) and [c["id"] for c in report["cues"]] == [c["id"] for c in plan["cues"]]
            and len({c["id"] for c in report["cues"]}) == len(report["cues"]), "Narration cue identities disagree")
    previous_end, words, speech_seconds = 0.0, 0, 0.0
    for actual, intended in zip(report["cues"], plan["cues"]):
        start, end = anchor_time(timeline, intended["start"]), anchor_time(timeline, intended["end"])
        require(actual["start_ms"] == start and actual["window_end_ms"] == end
                and 0 <= start < end <= 98550 and start >= previous_end, "Narration cue anchor or order mismatch")
        focus = focus_window(timeline, intended["visual_focus"], intended["focus_mode"])
        require(actual["visual_focus"] == intended["visual_focus"] and actual["focus_mode"] == intended["focus_mode"]
                and actual["resolved_visual_focus"] == focus
                and start >= focus["start_ms"] + plan["minimum_focus_settle_ms"]
                and end <= focus["end_ms"] - plan["focus_exit_guard_ms"], "Narration phrase crosses its settled semantic focus")
        selected = actual["selected"]
        require(selected["variant"] in {"primary", "short"}, "Unknown narration wording")
        text = intended["text"] if selected["variant"] == "primary" else intended["short_text"]
        count = len(re.findall(r"\b[A-Za-z0-9]+(?:['’][A-Za-z0-9]+)*\b", text))
        require(selected["text"] == text and selected["word_count"] == count and 145 <= selected["rate_wpm"] <= 180, "Narration wording or rate changed")
        require(type(selected["samples"]) is int and selected["samples"] > 0
                and abs(finite(selected["duration_seconds"]) - selected["samples"] / RATE) < 1e-9, "Invalid measured cue length")
        actual_end = (round(start * RATE / 1000) + selected["samples"]) * 1000 / RATE
        require(abs(finite(actual["actual_end_ms"]) - actual_end) < 1e-6
                and abs(finite(actual["remaining_window_ms"]) - (end - actual_end)) < 1e-6
                and end - actual_end >= plan["tail_guard_ms"] - 1000 / RATE, "Narration clip exceeds its measured window")
        previous_end, words, speech_seconds = end, words + count, speech_seconds + selected["samples"] / RATE
    require(words == report["spoken_word_count"] <= plan["max_words"]
            and abs(finite(report["spoken_audio_seconds"]) - speech_seconds) < 1e-6, "Narration totals disagree")
    verification = report["voice_window_verification"]
    require(set(verification["non_silent_intervals_per_cue"]) == {c["id"] for c in report["cues"]}
            and all(type(n) is int and n > 0 for n in verification["non_silent_intervals_per_cue"].values()), "An actual narration cue is silent")
    for start, end in verification["active_intervals_seconds"]:
        matches = [c for c in report["cues"] if start >= c["start_ms"] / 1000 - .04 and end <= c["window_end_ms"] / 1000 + .04]
        require(0 <= start < end <= DURATION and len(matches) == 1, "Speech activity escaped its window")
    video_probe(report["source_video_probe"], final=False)
    video_probe(report["output_probe"], final=True)
    packets = report["encoded_video_sha256"]
    require(set(packets) == {"source", "output"} and HASH.fullmatch(packets["source"])
            and packets["source"] == packets["output"], "Encoded H.264 packets changed")
    measurement = report["final_aac_measurement"]
    integrated, peak = finite(report["measured_integrated_lufs"]), finite(report["measured_true_peak_dbtp"])
    require(abs(integrated + 18) <= .5 and peak <= -2
            and integrated == finite(measurement["input_i"]) and peak == finite(measurement["input_tp"]), "Final measured loudness failed")
    commands = {}
    for command in report["commands"]:
        label = command["label"]
        require(label not in commands and command["status"] == "completed" and type(command["exit_code"]) is int
                and command["exit_code"] == 0 and type(command["pid"]) is int and command["pid"] > 0, "Narration command did not complete")
        argv = command["argv"]
        require(isinstance(argv, list) and argv and all(isinstance(x, str) for x in argv)
                and argv[0] in {SAY, FFMPEG, FFPROBE} and all("://" not in x for x in argv), "Unexpected narration command or network input")
        for kind in ("stdout", "stderr"):
            log = regular(command[kind])
            require(log.parent == out / "commands" and digest(log) == command[kind + "_sha256"], "Narration command log changed")
        commands[label] = command
    require(PROOF_COMMANDS <= set(commands) and any(c["argv"][0] == SAY and c["label"].startswith("say-") for c in commands.values()), "Required narration proof command is missing")
    for label, value in (("source-video-packets", packets["source"]), ("narrated-video-packets", packets["output"])):
        require(Path(commands[label]["stdout"]).read_text().strip().lower() == "sha256=" + value, "Packet hash log mismatch")
    require(json.loads(Path(commands["source-video-probe"]["stdout"]).read_bytes()) == report["source_video_probe"]
            and json.loads(Path(commands["narrated-film-probe"]["stdout"]).read_bytes()) == report["output_probe"], "Probe logs disagree with receipt")
    blocks = re.findall(r'\{\s*"input_i".*?\}', Path(commands["final-aac-loudness"]["stderr"]).read_text(), re.S)
    require(blocks and json.loads(blocks[-1]) == measurement, "Loudness log disagrees with receipt")
    require(voice["installed_inventory_line"] in Path(commands["installed-voices"]["stdout"]).read_text().splitlines(), "Installed voice log mismatch")
    return {"report": report, "out": out, "film": film, "plan": plan, "commands": commands,
            "input_paths": paths_by_name, "helper": helper}


class CopyPlan:
    def __init__(self):
        self.files = {}

    def add(self, source, name, expected=None):
        source = regular(source)
        safe_relative(name)
        require(name not in self.files, "Duplicate bundle destination")
        require(source.suffix.lower() in {".json", ".txt", ".py", ".mp4", ".srt"}, "Unsupported supplement file type")
        require(source.name not in PRIVATE_FILENAMES, "Private readback or seed is excluded")
        require(not any(part in {"clips", "node_modules", "__pycache__"} for part in source.parts), "Intermediate payload is excluded")
        actual = digest(source)
        require(expected is None or actual == expected, "Supplement input hash mismatch")
        if source.suffix.lower() == ".json":
            safe_json(read(source))
        if source.suffix.lower() != ".mp4":
            safe_text(source.read_text())
        self.files[name] = {"file": name, "source_path": str(source), "sha256": actual, "bytes": source.stat().st_size}


def pack(args):
    require(HASH.fullmatch(args.inputs_sha256), "Expected pack-input SHA-256 is required")
    input_path = hashed_file({"path": str(args.inputs), "sha256": args.inputs_sha256})
    inputs = read(input_path)
    required = {"contract", "source_commit", "narration_receipt", "strict_prepared", "commander_terminal"}
    require(required <= set(inputs) <= required | {"subtitles"}
            and inputs["contract"] == "casepath.documentary-narration-pack-inputs/1"
            and inputs["source_commit"] == SOURCE, "Unexpected pack input contract or source")
    require(not os.path.lexists(RUNTIME), "Preserve/reconcile the existing supplement attempt")
    binding = source_clean()
    narration_path, strict_path, terminal_path = (hashed_file(inputs[name]) for name in ("narration_receipt", "strict_prepared", "commander_terminal"))
    strict = strict_evidence(strict_path, binding)
    narration = narration_evidence(narration_path, binding, strict)
    terminal = terminal_result(terminal_path, args.commander_session_id)
    report, out = narration["report"], narration["out"]
    copy = CopyPlan()
    for source, name, expected in (
        (narration["film"], "film/CasePath_Documentary_Narrated.mp4", report["output_sha256"]),
        (out / "narration-plan.json", "narration-plan.json", report["input_files"]["plan"]["sha256"]),
        (out / "render_documentary_narration.py", "helpers/render_documentary_narration.py", report["helper_sha256"]),
        (narration_path, "narration-receipt.json", inputs["narration_receipt"]["sha256"]),
        (out / "cue-timings.json", "cue-timings.json", None),
        (out / "input-bindings.json", "input-bindings.json", report["inputs_sha256"]),
        (narration["input_paths"]["timeline"], "timeline.json", report["input_files"]["timeline"]["sha256"]),
        (terminal_path, "terminals/narration-commander-terminal.json", inputs["commander_terminal"]["sha256"]),
        (strict_path, "provenance/strict-final-evidence-prepared.json", inputs["strict_prepared"]["sha256"]),
        (strict["folder"] / "evidence-manifest.json", "provenance/strict-evidence-manifest.json", strict["ready"]["manifest_sha256"]),
        (strict["folder"] / "release-acceptance.json", "provenance/strict-release-acceptance.json", None),
        (NS / "source-binding.json", "provenance/source-binding.json", report["source_binding"]["sha256"]),
        (input_path, "pack-input-bindings.json", args.inputs_sha256),
        (Path(__file__).resolve(), "helpers/narration_supplement.py", None),
    ):
        copy.add(source, name, expected)
    for label in sorted(PROOF_COMMANDS):
        command = narration["commands"][label]
        for kind in ("stdout", "stderr"):
            copy.add(Path(command[kind]), "proof-logs/" + label + "." + kind + ".txt", command[kind + "_sha256"])
    subtitle_files = list(out.glob("*.srt"))
    subtitle_row = report.get("subtitles")
    if subtitle_row is not None:
        descriptor = {key: subtitle_row[key] for key in ("path", "sha256")}
        subtitle = hashed_file(descriptor)
        require(subtitle.parent == out and subtitle.suffix == ".srt" and subtitle_files == [subtitle], "Bind the one actual adjacent SRT")
        require(subtitle_row["format"] == "srt" and subtitle_row["cues"] == len(report["cues"])
                and subtitle_row["burned_into_video"] is False, "Unexpected subtitle scope")
        require("subtitles" not in inputs or inputs["subtitles"] == descriptor, "Explicit subtitle binding disagrees with the narration receipt")
        validate_srt(subtitle, report["cues"])
        copy.add(subtitle, "film/CasePath_Documentary_Narrated.srt", subtitle_row["sha256"])
    elif "subtitles" in inputs:
        subtitle = hashed_file(inputs["subtitles"])
        require(subtitle.parent == out and subtitle.suffix == ".srt" and subtitle_files == [subtitle], "Bind the one actual adjacent SRT")
        validate_srt(subtitle, report["cues"])
        copy.add(subtitle, "film/CasePath_Documentary_Narrated.srt", inputs["subtitles"]["sha256"])
    else:
        require(not subtitle_files, "An existing adjacent SRT must be explicitly hash-bound and included")
    summary = {
        "contract": "casepath.documentary-narration-supplement/1", "status": "verified",
        "source_commit": SOURCE, "source_tree": binding["source_tree"],
        "source_manifest_sha256": binding["source_manifest_sha256"],
        "strict_evidence_destination": strict["destination"],
        "strict_prepared_sha256": inputs["strict_prepared"]["sha256"],
        "strict_manifest_sha256": strict["ready"]["manifest_sha256"],
        "narration_receipt_sha256": inputs["narration_receipt"]["sha256"],
        "commander_session_id": terminal["sessionId"], "commander_terminal_sha256": inputs["commander_terminal"]["sha256"],
        "narrated_film_sha256": report["output_sha256"], "narration_helper_sha256": report["helper_sha256"],
        "video_packets_unchanged": True, "encoded_video_sha256": report["encoded_video_sha256"]["output"],
        "video_frames": FRAMES, "fps": FPS, "width": 1920, "height": 1080, "duration_seconds": DURATION,
        "measured_integrated_lufs": report["measured_integrated_lufs"], "measured_true_peak_dbtp": report["measured_true_peak_dbtp"],
        "voice": report["voice"], "spoken_word_count": report["spoken_word_count"], "cue_count": len(report["cues"]),
        "provider_or_model_calls": False, "voice_downloads": False, "subjective_listening_claimed": False,
        "product_changes": False, "deployment_performed": False, "commit_or_push_performed": False,
    }
    strict_link = os.path.relpath(strict["destination"], DESTINATION)
    download = "https://github.com/KumarNavish/casepath/raw/refs/heads/" + CANONICAL_BRANCH + "/" + DESTINATION + "/film/CasePath_Documentary_Narrated.mp4"
    readme = f"""# CasePath narrated documentary

[Open the narrated film](film/CasePath_Documentary_Narrated.mp4) · [Download MP4]({download}) · [Original film and strict release evidence]({strict_link}/README.md)

Product source: `{SOURCE}`. This additional narrated edition uses the exact H.264 video packets from the strict film for that source: 2,957 frames, 1920 × 1080, 30 fps, {DURATION:.7f} seconds. The narration does not change the product, its recorded case outcomes, or the original film.

The installed macOS Daniel voice reads {report['spoken_word_count']} authored words in {len(report['cues'])} measured, phase-aligned windows. The original score is reduced during speech. Narration uses offline `/usr/bin/say`; there are no model/provider calls or voice downloads. The finished AAC audio measured {report['measured_integrated_lufs']:.2f} LUFS integrated and {report['measured_true_peak_dbtp']:.2f} dBTP true peak. The successful receipt verifies full decode, unchanged video packets, cue-window fit, and unchanged inputs. No subjective listening assessment is claimed by this package.

`narration-plan.json` contains the authored script and timing anchors. `cue-timings.json` records the actual selected words and measured clip lengths. `narration-receipt.json`, the exact renderer, input bindings, the source timeline, selected small proof logs, the actual Commander terminal result, and strict-release provenance accompany the MP4.{' A separate SRT is available beside the film.' if subtitle_files else ''}

`narration-manifest.json` enumerates every payload file and its exact SHA-256 and byte count; the prepared receipt outside this directory binds the manifest itself. Intermediate WAV/AIFF files, voice clips, PCM masters, private seed/readback data, credentials, and full frame directories are excluded.

This directory is a separate narration supplement. Its later evidence-only commit preserves the isolated product checkout at the source above and retains the existing strict evidence. Packaging does not claim a commit or push before those operations actually complete.
"""
    derived = {"README.md": readme, "narration-acceptance.json": json.dumps(summary, indent=2, ensure_ascii=False) + "\n"}
    require(not set(derived) & set(copy.files), "Derived filename collision")
    for parent in RUNTIME.parents:
        require(not parent.is_symlink(), "Symlink runtime ancestor")
    RUNTIME.mkdir(parents=True, mode=0o700)
    attempt = {"contract": "casepath.documentary-narration-pack-attempt/1", "status": "validated",
               "source_commit": SOURCE, "started_at": now(), "inputs_sha256": args.inputs_sha256,
               "helper_sha256": digest(Path(__file__).resolve()), "product_changes": False, "commit_or_push_performed": False}
    persist(PACK_ATTEMPT, attempt, first=True)
    try:
        BUNDLE.mkdir(mode=0o700)
        for name, row in sorted(copy.files.items()):
            target = BUNDLE / name
            target.parent.mkdir(parents=True, exist_ok=True)
            require(digest(row["source_path"]) == row["sha256"], "Input changed before packaging")
            with regular(row["source_path"]).open("rb") as src, target.open("xb") as dst:
                shutil.copyfileobj(src, dst, 1024 * 1024)
            require(digest(target) == row["sha256"] == digest(row["source_path"]), "Copy mismatch")
        for name, text in derived.items():
            with (BUNDLE / name).open("x", encoding="utf-8") as stream:
                stream.write(text)
        source_clean(binding)
        manifest = {
            "contract": "casepath.documentary-narration-manifest/1", "source_commit": SOURCE,
            "created_at": now(), "generator_sha256": attempt["helper_sha256"],
            "intended_repository_destination": DESTINATION, "product_changes": False, "commit_or_push_performed": False,
            "copies": list(copy.files.values()),
            "derived": [{"file": name, "sha256": digest(BUNDLE / name), "bytes": (BUNDLE / name).stat().st_size} for name in derived],
            "excluded": ["WAV/AIFF/PCM intermediates", "raw private state and seeds", "credentials", "full frame directories"],
        }
        manifest_path = BUNDLE / "narration-manifest.json"
        new_json(manifest_path, manifest)
        expected = manifest_files(manifest, manifest_path)
        exact_files(BUNDLE, expected)
        ready = {
            "contract": "casepath.documentary-narration-prepared/1", "status": "prepared", "source_commit": SOURCE,
            "source_tree": binding["source_tree"], "source_manifest_sha256": binding["source_manifest_sha256"],
            "bundle": str(BUNDLE), "manifest_sha256": digest(manifest_path), "files": len(expected),
            "intended_repository_destination": DESTINATION, "source_clean_after": True,
            "product_changes": False, "commit_or_push_performed": False, "helper_sha256": attempt["helper_sha256"],
            "strict_prepared": inputs["strict_prepared"], "strict_manifest_sha256": strict["ready"]["manifest_sha256"],
            "commander_session_id": args.commander_session_id, "prepared_at": now(),
        }
        new_json(READY, ready)
        attempt.update(status="prepared", finished_at=now(), prepared_receipt=str(READY), prepared_receipt_sha256=digest(READY))
        persist(PACK_ATTEMPT, attempt)
        print(json.dumps({"status": "prepared", "receipt": str(READY), "receipt_sha256": digest(READY),
                          "manifest_sha256": ready["manifest_sha256"], "files": len(expected), "destination": DESTINATION}), flush=True)
    except BaseException as error:
        attempt.update(status="failed_requires_reconciliation", finished_at=now(), error_type=type(error).__name__, error=str(error)[:1500])
        persist(PACK_ATTEMPT, attempt)
        raise


def verify_git_blobs(repository, revision, destination, expected):
    for name, row in expected.items():
        raw = git_bytes(repository, "show", revision + ":" + destination + "/" + name)
        require(len(raw) == row["bytes"] and hashlib.sha256(raw).hexdigest() == row["sha256"], "Git blob differs: " + name)


def canonical_at(expected):
    require(git(CANONICAL, "branch", "--show-current") == CANONICAL_BRANCH, "Wrong canonical branch")
    require(git(CANONICAL, "rev-parse", "HEAD") == expected, "Canonical HEAD changed")
    require(git(CANONICAL, "status", "--porcelain", "--untracked-files=all") == "", "Canonical checkout must be clean")
    fetch = git(CANONICAL, "remote", "get-url", "--all", "origin").splitlines()
    push = git(CANONICAL, "remote", "get-url", "--push", "--all", "origin").splitlines()
    require(len(fetch) == len(push) == 1 and fetch[0] in ALLOWED_REMOTES and push[0] in ALLOWED_REMOTES, "Canonical origin must be the exact CasePath repository")
    mirror = git_result(CANONICAL, "config", "--get", "--bool", "remote.origin.mirror")
    require(mirror.returncode == 1 or mirror.returncode == 0 and mirror.stdout.strip() == b"false", "Mirror push is forbidden")


def remote_at(expected):
    require(git(CANONICAL, "ls-remote", "--heads", "origin", REFERENCE) == expected + "\t" + REFERENCE, "Remote branch differs from explicit expected HEAD")


def new_paths_only(repository, old, new, destination, expected):
    wanted = {destination + "/" + name for name in expected}
    changed = set(paths(git_bytes(repository, "diff", "--name-only", "-z", old, new)))
    require(changed == wanted, "Commit changes files outside the exact new supplement")
    status = git(repository, "diff", "--name-status", "--no-renames", old, new).splitlines()
    require(len(status) == len(wanted) and all(row.startswith("A\t" + destination + "/") for row in status), "Only newly added supplement files are allowed")


def commit(args):
    expected_head = args.expected_canonical_head
    require(COMMIT.fullmatch(expected_head) and expected_head != SOURCE, "Pass the actual strict-evidence canonical HEAD explicitly")
    prepared = hashed_file({"path": str(args.prepared), "sha256": args.prepared_sha256})
    require(prepared == READY, "Use this source's prepared narration receipt")
    require(not os.path.lexists(COMMIT_ATTEMPT) and not os.path.lexists(LOGS), "Reconcile the original commit attempt; do not retry")
    require(not os.path.lexists(WORKTREE), "A fresh evidence worktree is required")
    binding = source_clean()
    ready = read(prepared)
    require(ready["contract"] == "casepath.documentary-narration-prepared/1" and ready["status"] == "prepared"
            and ready["source_commit"] == SOURCE and ready["source_tree"] == binding["source_tree"]
            and ready["source_manifest_sha256"] == binding["source_manifest_sha256"], "Wrong prepared narration source")
    require(ready["bundle"] == str(BUNDLE) and ready["intended_repository_destination"] == DESTINATION
            and ready["source_clean_after"] is True and ready["product_changes"] is False
            and ready["commit_or_push_performed"] is False, "Unexpected narration preparation state")
    require(ready["helper_sha256"] == digest(Path(__file__).resolve()), "Packer/commit helper changed after preparation")
    pack_attempt = read(PACK_ATTEMPT)
    require(pack_attempt["status"] == "prepared" and pack_attempt["source_commit"] == SOURCE
            and pack_attempt["prepared_receipt"] == str(READY)
            and pack_attempt["prepared_receipt_sha256"] == args.prepared_sha256
            and pack_attempt["helper_sha256"] == ready["helper_sha256"], "The pack attempt did not finish successfully")
    strict = strict_evidence(hashed_file(ready["strict_prepared"]), binding)
    require(strict["ready"]["manifest_sha256"] == ready["strict_manifest_sha256"], "Strict evidence changed after narration preparation")
    manifest_path = regular(BUNDLE / "narration-manifest.json")
    require(digest(manifest_path) == ready["manifest_sha256"], "Narration manifest changed")
    manifest = read(manifest_path)
    require(manifest["contract"] == "casepath.documentary-narration-manifest/1" and manifest["source_commit"] == SOURCE
            and manifest["intended_repository_destination"] == DESTINATION and manifest["generator_sha256"] == ready["helper_sha256"]
            and manifest["product_changes"] is False and manifest["commit_or_push_performed"] is False, "Narration manifest identity changed")
    expected = manifest_files(manifest, manifest_path)
    require(len(expected) == ready["files"], "Narration file count mismatch")
    exact_files(BUNDLE, expected)
    acceptance = read(BUNDLE / "narration-acceptance.json")
    require(acceptance["source_commit"] == SOURCE and acceptance["strict_manifest_sha256"] == ready["strict_manifest_sha256"], "Narration acceptance mismatch")
    canonical_at(expected_head)
    remote_at(expected_head)
    require(git_result(CANONICAL, "merge-base", "--is-ancestor", SOURCE, expected_head).returncode == 0, "Canonical HEAD does not descend from the sealed product")
    require(git(CANONICAL, "ls-tree", "-r", "--name-only", expected_head, "--", DESTINATION) == "", "Narration destination already exists")
    require(git(CANONICAL, "ls-tree", "-r", "--name-only", SOURCE, "--", strict["destination"]) == "", "Strict evidence is not newly added after this source")
    new_paths_only(CANONICAL, SOURCE, expected_head, strict["destination"], strict["expected"])
    verify_git_blobs(CANONICAL, expected_head, strict["destination"], strict["expected"])
    require(hashlib.sha256(git_bytes(CANONICAL, "show", expected_head + ":casepath/source-manifest.json")).hexdigest() == binding["source_manifest_sha256"], "Canonical product manifest differs")
    require(git_result(CANONICAL, "show-ref", "--verify", "--quiet", "refs/heads/" + EVIDENCE_BRANCH).returncode == 1, "Evidence branch already exists")
    state = {
        "contract": "casepath.documentary-narration-commit/1", "status": "validated", "started_at": now(),
        "source_commit": SOURCE, "source_tree": binding["source_tree"], "source_manifest_sha256": binding["source_manifest_sha256"],
        "expected_canonical_head": expected_head, "canonical_branch": CANONICAL_BRANCH, "evidence_branch": EVIDENCE_BRANCH,
        "worktree": str(WORKTREE), "bundle": str(BUNDLE), "destination": DESTINATION,
        "prepared_receipt_sha256": args.prepared_sha256, "manifest_sha256": ready["manifest_sha256"],
        "helper_sha256": ready["helper_sha256"], "product_changes": False, "deployment_performed": False,
        "force_push": False, "retries": 0, "steps": [],
    }
    active = None

    def stop_child():
        nonlocal active
        if active is not None and active.poll() is None:
            try:
                os.killpg(active.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                active.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(active.pid, signal.SIGKILL)
                active.wait(timeout=10)
        active = None

    def command(name, cwd, argv, timeout=120):
        nonlocal active
        log = LOGS / (name + ".log")
        row = {"name": name, "cwd": str(cwd), "argv": [GIT, *argv], "status": "requested",
               "requested_at": now(), "log": str(log)}
        state["steps"].append(row)
        persist(COMMIT_ATTEMPT, state)
        with log.open("xb") as stream:
            active = subprocess.Popen(row["argv"], cwd=cwd, env=ENV, stdin=subprocess.DEVNULL,
                                      stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
            row.update(status="running", pid=active.pid, started_at=now())
            persist(COMMIT_ATTEMPT, state)
            try:
                code = active.wait(timeout=timeout)
            except BaseException:
                stop_child()
                row.update(status="interrupted_or_timed_out", finished_at=now(), outcome_requires_reconciliation=True)
                persist(COMMIT_ATTEMPT, state)
                raise
            active = None
            stream.flush()
            os.fsync(stream.fileno())
        row.update(status="completed" if code == 0 else "failed", exit_code=code, finished_at=now(), log_sha256=digest(log))
        persist(COMMIT_ATTEMPT, state)
        require(code == 0, "Git mutation failed; reconcile the recorded attempt: " + name)

    def interrupted(signum, _frame):
        raise SystemExit(128 + signum)

    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    persist(COMMIT_ATTEMPT, state, first=True)
    try:
        LOGS.mkdir(mode=0o700)
        command("01-worktree", CANONICAL, ["worktree", "add", "-b", EVIDENCE_BRANCH, str(WORKTREE), expected_head])
        require(git(WORKTREE, "rev-parse", "HEAD") == expected_head and git(WORKTREE, "branch", "--show-current") == EVIDENCE_BRANCH
                and git(WORKTREE, "status", "--porcelain", "--untracked-files=all") == "", "Unexpected new worktree state")
        target = WORKTREE / DESTINATION
        require(not os.path.lexists(target), "Narration destination already exists")
        state["status"] = "copying_verified_bundle"
        persist(COMMIT_ATTEMPT, state)
        target.mkdir(parents=True)
        for name, row in sorted(expected.items()):
            source, output = regular(BUNDLE / name), target / name
            output.parent.mkdir(parents=True, exist_ok=True)
            require(digest(source) == row["sha256"], "Bundle changed before commit")
            with source.open("rb") as src, output.open("xb") as dst:
                shutil.copyfileobj(src, dst, 1024 * 1024)
        exact_files(BUNDLE, expected)
        exact_files(target, expected)
        wanted = {DESTINATION + "/" + name for name in expected}
        require(git(WORKTREE, "diff", "--name-only") == ""
                and set(paths(git_bytes(WORKTREE, "ls-files", "--others", "--exclude-standard", "-z"))) == wanted, "Unexpected working changes before staging")
        command("02-stage", WORKTREE, ["add", "--", DESTINATION])
        require(set(paths(git_bytes(WORKTREE, "diff", "--cached", "--name-only", "-z"))) == wanted, "Unexpected staged files")
        statuses = git(WORKTREE, "diff", "--cached", "--name-status", "--no-renames").splitlines()
        require(len(statuses) == len(wanted) and all(row.startswith("A\t" + DESTINATION + "/") for row in statuses), "Only new narration files may be staged")
        require(git(WORKTREE, "diff", "--name-only") == "" and git(WORKTREE, "ls-files", "--others", "--exclude-standard") == "", "Unstaged work appeared")
        verify_git_blobs(WORKTREE, "", DESTINATION, expected)
        command("03-commit", WORKTREE, ["commit", "-m", "Add verified narrated CasePath documentary supplement"])
        evidence = git(WORKTREE, "rev-parse", "HEAD")
        require(COMMIT.fullmatch(evidence) and git(WORKTREE, "rev-list", "--parents", "-n", "1", "HEAD").split() == [evidence, expected_head], "Unexpected narration commit parent")
        new_paths_only(WORKTREE, expected_head, evidence, DESTINATION, expected)
        require(git(WORKTREE, "status", "--porcelain", "--untracked-files=all") == "", "Evidence worktree is not clean")
        verify_git_blobs(WORKTREE, evidence, DESTINATION, expected)
        exact_files(target, expected)
        source_clean(binding)
        state.update(status="narration_commit_verified", evidence_commit=evidence, evidence_tree=git(WORKTREE, "rev-parse", "HEAD^{tree}"))
        persist(COMMIT_ATTEMPT, state)
        canonical_at(expected_head)
        remote_at(expected_head)
        require(digest(prepared) == args.prepared_sha256 and digest(manifest_path) == ready["manifest_sha256"], "Prepared evidence changed before publication")
        command("04-canonical-fast-forward", CANONICAL, ["merge", "--ff-only", evidence])
        canonical_at(evidence)
        remote_at(expected_head)
        source_clean(binding)
        state["status"] = "push_requested"
        persist(COMMIT_ATTEMPT, state)
        command("05-normal-push", CANONICAL, ["-c", "http.postBuffer=268435456", "-c", "http.version=HTTP/1.1",
                                             "push", "--porcelain", "origin", evidence + ":" + REFERENCE], timeout=180)
        remote_at(evidence)
        canonical_at(evidence)
        source_clean(binding)
        require(git(WORKTREE, "rev-parse", "HEAD") == evidence and git(WORKTREE, "status", "--porcelain") == "", "Evidence worktree changed")
        state.update(status="pushed_and_verified", finished_at=now(), remote_commit=evidence, product_clone_head=SOURCE, product_clone_clean=True)
        persist(COMMIT_ATTEMPT, state)
        print(json.dumps({"status": state["status"], "narration_commit": evidence, "product_source_commit": SOURCE,
                          "receipt": str(COMMIT_ATTEMPT), "worktree": str(WORKTREE), "destination": DESTINATION}), flush=True)
    except BaseException as error:
        stop_child()
        state.update(status="failed_requires_reconciliation", finished_at=now(), error_type=type(error).__name__, error=str(error)[:1500])
        persist(COMMIT_ATTEMPT, state)
        raise
    finally:
        stop_child()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    packing = commands.add_parser("pack", help="Validate actual successful inputs and prepare a fresh runtime bundle")
    packing.add_argument("--inputs", type=Path, required=True)
    packing.add_argument("--inputs-sha256", required=True)
    packing.add_argument("--commander-session-id", required=True)
    packing.set_defaults(run=pack)
    committing = commands.add_parser("commit", help="Commit and normally push only the prepared supplement")
    committing.add_argument("--prepared", type=Path, required=True)
    committing.add_argument("--prepared-sha256", required=True)
    committing.add_argument("--expected-canonical-head", required=True)
    committing.set_defaults(run=commit)
    args = parser.parse_args()
    require(sys.platform == "darwin", "Production packing/commit runs only on the owner's Mac")
    args.run(args)


if __name__ == "__main__":
    main()
