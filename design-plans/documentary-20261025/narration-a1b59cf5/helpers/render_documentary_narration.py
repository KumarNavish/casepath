#!/usr/bin/env python3
"""Render an additional offline Daniel narration without changing the film.

Run on the Mac only after the new public film and original-score master exist.
Pass an exact hash-bound input manifest. Every input is read-only; the output
directory must be new and outside the bound cinema release namespace. This
helper renders authored text with the already installed Daniel voice, verifies
each actual clip length, ducks the existing score, and copies H.264 packets.
It never downloads a voice or calls a provider/model/network service.
"""
from __future__ import annotations

if not __debug__:
    raise RuntimeError("Assertions must remain enabled")

import argparse
from array import array
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import textwrap
import wave

sys.dont_write_bytecode = True
ROOT = Path("/Users/kumar0002/Documents/Die Mobiliar/.work/casepath-commander-documentary-20261024")
OUTPUT_ROOT = ROOT / ".runtime/cinema-evidence/audio-20261025"
SAY = Path("/usr/bin/say")
FFMPEG = Path("/Users/kumar0002/.local/bin/ffmpeg")
FFPROBE = Path("/Users/kumar0002/.local/bin/ffprobe")
RATE = 48000
REQUIRED_FILES = {"silent_video", "score_master", "capture_receipt", "media_receipt", "timeline", "plan"}


def now():
    return datetime.now(timezone.utc).isoformat()


def regular(value):
    path = Path(value)
    assert path.is_absolute() and ".." not in path.parts
    assert path.is_relative_to(ROOT / ".runtime"), str(path)
    assert path.is_file() and not path.is_symlink(), str(path)
    for parent in path.parents:
        assert not parent.is_symlink(), str(parent)
        if parent == ROOT:
            break
    return path


def digest(path):
    path = Path(path)
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


def word_count(text):
    return len(re.findall(r"\b[A-Za-z0-9]+(?:['’][A-Za-z0-9]+)*\b", text))


def anchor_time(timeline, anchor):
    assert set(anchor) == {"act", "phase", "edge", "offset_ms", "occurrence"}
    beats = [beat for beat in timeline["beats"]
             if beat["act"] == anchor["act"] and beat["phase"] == anchor["phase"]]
    assert beats, (anchor["act"], anchor["phase"])
    index = anchor["occurrence"]
    assert type(index) is int and (index == -1 or 0 <= index < len(beats))
    assert anchor["edge"] in {"start", "end"} and type(anchor["offset_ms"]) is int
    return beats[index][anchor["edge"]] + anchor["offset_ms"]


def focus_window(timeline, selector, mode):
    """Resolve a semantic cue after entering transitions hide its spotlight."""
    assert isinstance(selector, dict) and set(selector) <= {"id", "target", "target_id"}
    assert isinstance(selector.get("id"), str) and selector["id"]
    assert mode in {"spotlight", "chapter-framing"}
    assert isinstance(timeline.get("guidance"), list) and timeline["guidance"]
    rows = [row for row in timeline["guidance"]
            if row.get("id") == selector["id"]
            and ("target" not in selector or row.get("target") == selector["target"])
            and ("target_id" not in selector or row.get("targetId") == selector["target_id"])]
    assert rows, "No matching visual focus: " + str(selector)
    if mode == "spotlight":
        assert all(row.get("spotlight") is True for row in rows), "Cue has no spotlight: " + str(selector)
    else:
        assert selector["id"] in {"question", "finale"}, "Only introduction and finale are chapter framing"
    rows.sort(key=lambda row: row["start"])
    start, end = rows[0]["start"], rows[0]["start"]
    for row in rows:
        assert type(row["start"]) is int and type(row["end"]) is int
        assert 0 <= row["start"] < row["end"] <= timeline["duration"]
        assert row["start"] == end, "Ambiguous or discontinuous visual focus: " + str(selector)
        end = row["end"]
    visible_start = start
    transitions = [] if mode == "chapter-framing" else sorted((beat for beat in timeline["beats"]
                          if beat["phase"] in {"act-transition", "scene-transition"}
                          and beat["start"] < end and beat["end"] > start), key=lambda beat: beat["start"])
    for beat in transitions:
        assert beat["start"] <= visible_start, "Visual cue interrupted by a hidden transition: " + str(selector)
        visible_start = max(visible_start, beat["end"])
    assert visible_start < end
    return {"selector": selector, "mode": mode, "guidance_start_ms": start,
            "start_ms": visible_start, "end_ms": end, "guidance_segments": len(rows),
            "excluded_entering_transition_ms": visible_start - start,
            "settle_reference": "chapter-cue-start" if mode == "chapter-framing" else "visible-spotlight-arrival"}


def resolve_cues(plan, timeline):
    """Require each authored phrase to stay inside its exact settled focus."""
    assert plan["max_words"] == 110 and 0 <= plan["tail_guard_ms"] <= 500
    count = plan["reviewed_cue_count"]
    assert type(count) is int and 1 <= count <= 24
    assert 300 <= plan["minimum_focus_settle_ms"] <= 1000
    assert 0 <= plan["focus_exit_guard_ms"] <= 500
    assert plan["exclude_entering_transitions"] is True
    cues, previous_end = [], 0
    for cue in plan["cues"]:
        assert re.fullmatch("[a-z][a-z0-9-]+", cue["id"])
        for text_key, count_key in [("text", "word_count"), ("short_text", "short_word_count")]:
            text = cue[text_key]
            assert isinstance(text, str) and text and len(text) < 400
            assert "[[" not in text and "]]" not in text and "\n" not in text
            assert word_count(text) == cue[count_key]
        start, end = anchor_time(timeline, cue["start"]), anchor_time(timeline, cue["end"])
        assert 0 <= start < end <= timeline["duration"] and start >= previous_end
        assert end - start - plan["tail_guard_ms"] > 1500
        focus = focus_window(timeline, cue["visual_focus"], cue["focus_mode"])
        assert start >= focus["start_ms"] + plan["minimum_focus_settle_ms"], "Speech precedes settled focus: " + cue["id"]
        assert end <= focus["end_ms"] - plan["focus_exit_guard_ms"], "Speech window crosses a focus change: " + cue["id"]
        cues.append({**cue, "start_ms": start, "window_end_ms": end, "resolved_visual_focus": focus})
        previous_end = end
    assert len({cue["id"] for cue in cues}) == len(cues) == count
    assert {cue["id"] for cue in cues if cue["focus_mode"] == "chapter-framing"} == {"question", "finale"}
    assert sum(cue["word_count"] for cue in cues) == plan["primary_word_count"] <= plan["max_words"]
    assert sum(max(cue["word_count"], cue["short_word_count"]) for cue in cues) <= plan["max_words"]
    return cues


def srt_for_cues(cues):
    """Sidecar captions use actual chosen wording and rendered clip boundaries."""
    def timestamp(milliseconds):
        hours, remainder = divmod(milliseconds, 3600000)
        minutes, remainder = divmod(remainder, 60000)
        seconds, millis = divmod(remainder, 1000)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"

    rows, previous_end = [], 0
    for index, cue in enumerate(cues, 1):
        start, end = round(cue["start_ms"]), round(cue["actual_end_ms"])
        assert start >= previous_end and end > start
        text = cue["selected"]["text"]
        assert isinstance(text, str) and text and "\n" not in text
        lines = textwrap.wrap(text, width=42, break_long_words=False, break_on_hyphens=False)
        rows.append(f"{index}\n{timestamp(start)} --> {timestamp(end)}\n" + "\n".join(lines))
        previous_end = end
    assert rows
    return "\n\n".join(rows) + "\n"


def loudness_json(text):
    blocks = re.findall(r'\{\s*"input_i".*?\}', text, flags=re.S)
    assert blocks, "FFmpeg did not return a loudnorm measurement"
    row = json.loads(blocks[-1])
    for key in ("input_i", "input_tp", "input_lra", "input_thresh", "target_offset"):
        assert math.isfinite(float(row[key])), (key, row[key])
    return row


def new_bytes(path, raw):
    assert not path.exists()
    with path.open("xb") as stream:
        stream.write(raw)


def make_duck_expression(cues, mix):
    """Frame-evaluated music gain; ramps start before the actual spoken clips."""
    attack = mix["duck_attack_ms"] / 1000
    hold = mix["duck_hold_ms"] / 1000
    release = mix["duck_release_ms"] / 1000
    assert 0.1 <= attack <= 0.5 and 0 <= hold <= 0.5 and 0.3 <= release <= 1.5
    envelopes = []
    for cue in cues:
        start = cue["start_ms"] / 1000
        end = cue["actual_end_ms"] / 1000
        a, b, c, d = start - attack, start, end + hold, end + hold + release
        envelopes.append(
            f"if(lt(t,{a:.9f}),0,if(lt(t,{b:.9f}),(t-{a:.9f})/{attack:.9f},"
            f"if(lt(t,{c:.9f}),1,if(lt(t,{d:.9f}),({d:.9f}-t)/{release:.9f},0))))")
    envelope = envelopes[0]
    for item in envelopes[1:]:
        envelope = f"max({envelope},{item})"
    baseline = 10 ** (mix["music_baseline_db"] / 20)
    under = 10 ** (mix["music_under_voice_extra_db"] / 20)
    assert 0 < baseline <= 1 and 0 < under < 1
    return f"if(isnan(t),{baseline:.12f},{baseline:.12f}*(1-{1-under:.12f}*({envelope})))"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--inputs-sha256", required=True)
    args = parser.parse_args()
    assert sys.platform == "darwin", "Render only with the installed Mac Daniel voice"
    assert re.fullmatch("[0-9a-f]{64}", args.inputs_sha256)
    input_path = regular(args.inputs)
    assert digest(input_path) == args.inputs_sha256
    inputs = read(input_path)
    assert inputs["contract"] == "casepath.documentary-narration-inputs/1"
    source = inputs["source_commit"]
    assert re.fullmatch("[0-9a-f]{40}", source)
    source_binding_path = regular(ROOT / ".runtime/documentary-release-20261025/source-binding.json")
    source_binding = read(source_binding_path)
    source_binding_sha = digest(source_binding_path)
    assert source_binding["source_commit"] == source
    assert source_binding["base_commit"] == "5da3233a0aa04ad29843c8ec55dfb685118381c9"
    assert source_binding["branch"] == 'codex/casepath-documentary-20261025'
    assert set(inputs["files"]) == REQUIRED_FILES
    paths = {}
    for name, row in inputs["files"].items():
        assert set(row) == {"path", "sha256"} and re.fullmatch("[0-9a-f]{64}", row["sha256"])
        paths[name] = regular(row["path"])
        assert digest(paths[name]) == row["sha256"], name
    plan, capture, media, timeline = (read(paths[name]) for name in ["plan", "capture_receipt", "media_receipt", "timeline"])
    assert plan["contract"] == "casepath.documentary-narration-plan/1"
    assert plan["voice"] == "Daniel" and plan["language"] == "en-GB" and plan["engine"] == str(SAY)
    assert plan["provider_or_model_calls"] is False and plan["downloads"] is False
    assert (plan["min_rate_wpm"], plan["preferred_rate_wpm"], plan["max_rate_wpm"]) == (145, 155, 180)
    assert capture["source_commit"] == source and capture["status"] == "passed"
    assert capture["mode"] == "deployed_read_only_replay" and capture["new_inference"] is False
    assert capture["health"]["source_commit"] == capture["deployment"]["source_commit"] == source
    assert capture["health"]["read_only"] is True and capture["health"]["writable"] is False
    assert capture["browser_errors"] == capture["writes"] == capture["unexpected_destinations"] == []
    assert timeline == capture["timeline"] and timeline["duration"] == plan["planned_duration_ms"] == 98550
    assert plan["fps"] == capture["fps"] == 30
    frames = math.ceil(timeline["duration"] * 30 / 1000)
    assert frames == capture["frame_count"] == 2957
    duration = frames / 30
    samples = frames * (RATE // 30)
    assert capture["video"]["sha256"] == inputs["files"]["silent_video"]["sha256"]
    assert paths["capture_receipt"].parent / capture["video"]["file"] == paths["silent_video"]
    assert media["passed"] is True and media["originals_unchanged"] is True and media["video_reencoding"] is False
    assert Path(media["silent"]) == paths["silent_video"]
    assert media["input_sha256"]["silent"] == inputs["files"]["silent_video"]["sha256"]
    assert media["pcm_master_sha256"] == inputs["files"]["score_master"]["sha256"]
    assert media["video_frames"] == frames and media["audio_pcm_samples"] == samples
    assert abs(media["duration_seconds"] - duration) < 1e-6
    scored_original = regular(media["output"])
    assert digest(scored_original) == media["output_sha256"]
    assert abs(media["measured_integrated_lufs"] + 20) <= 0.5 and media["measured_true_peak_dbtp"] <= -2
    cues = resolve_cues(plan, timeline)
    out_dir = Path(inputs["out_dir"])
    assert out_dir.is_absolute() and ".." not in out_dir.parts and out_dir.is_relative_to(OUTPUT_ROOT)
    assert out_dir != OUTPUT_ROOT and not out_dir.exists(), "Use a fresh narration output directory; preserve any prior attempt"
    assert all(not path.is_relative_to(out_dir) for path in [input_path, *paths.values(), scored_original])
    for parent in out_dir.parents:
        assert not parent.is_symlink()
        if parent == ROOT:
            break
    for binary in (SAY, FFMPEG, FFPROBE):
        assert binary.is_file() and os.access(binary, os.X_OK), str(binary)

    out_dir.mkdir(parents=True)
    logs = out_dir / "commands"
    clips = out_dir / "clips"
    logs.mkdir()
    clips.mkdir()
    receipt_path = out_dir / "narration-receipt.json"
    output = out_dir / "CasePath_Documentary_Narrated.mp4"
    report = {
        "contract": "casepath.documentary-narration/1", "status": "running", "passed": False,
        "source_commit": source, "started_at": now(), "inputs_sha256": args.inputs_sha256,
        "source_binding": {"path": str(source_binding_path), "sha256": source_binding_sha},
        "input_files": inputs["files"], "existing_scored_film": {"path": str(scored_original), "sha256": media["output_sha256"]},
        "helper_path": str(Path(__file__).resolve()), "helper_sha256": digest(__file__),
        "voice": {"name": "Daniel", "language": "en-GB", "engine": str(SAY), "speed_range_wpm": [145, 180]},
        "network_commands": False, "provider_or_model_calls": False, "voice_downloads": False,
        "originals_unchanged": False, "video_reencoding": False, "subjective_listening_claimed": False,
        "duration_seconds": duration, "video_frames": frames, "audio_pcm_samples": samples,
        "output": str(output), "commands": [], "cues": [], "mix_plan": plan["mix"],
        "reviewed_cue_count": plan["reviewed_cue_count"], "max_words": plan["max_words"],
        "focus_policy": {"minimum_settle_ms": plan["minimum_focus_settle_ms"],
                         "exit_guard_ms": plan["focus_exit_guard_ms"],
                         "entering_transitions_excluded": True,
                         "spotlight_clips": sum(cue["focus_mode"] == "spotlight" for cue in cues),
                         "chapter_framing_clips": sum(cue["focus_mode"] == "chapter-framing" for cue in cues),
                         "all_windows_within_matching_cue": True},
    }
    environment = {key: os.environ[key] for key in ("HOME", "USER", "LOGNAME", "TMPDIR") if key in os.environ}
    environment.update(PATH="/usr/bin:/bin:/usr/sbin:/sbin:/Users/kumar0002/.local/bin", LANG="en_GB.UTF-8", LC_ALL="en_GB.UTF-8", TZ="UTC")
    active = None

    def persist():
        temporary = receipt_path.with_suffix(".next")
        temporary.write_text(json.dumps(report, indent=2) + "\n")
        os.replace(temporary, receipt_path)

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

    def interrupted(signum, _frame):
        raise SystemExit(128 + signum)

    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)

    def run(label, argv, timeout=300):
        nonlocal active
        assert re.fullmatch("[a-z0-9-]+", label)
        prefix = f"{len(report['commands'])+1:03d}-{label}"
        stdout_path, stderr_path = logs / (prefix + ".stdout.txt"), logs / (prefix + ".stderr.txt")
        row = {"label": label, "argv": [str(arg) for arg in argv], "status": "running", "started_at": now(),
               "stdout": str(stdout_path), "stderr": str(stderr_path)}
        report["commands"].append(row)
        persist()
        with stdout_path.open("xb") as stdout, stderr_path.open("xb") as stderr:
            active = subprocess.Popen(row["argv"], cwd=ROOT, env=environment, stdin=subprocess.DEVNULL,
                                      stdout=stdout, stderr=stderr, start_new_session=True)
            row["pid"] = active.pid
            persist()
            try:
                code = active.wait(timeout=timeout)
            except BaseException:
                stop_child()
                row.update(status="interrupted", finished_at=now())
                persist()
                raise
            active = None
        row.update(exit_code=code, status="completed" if code == 0 else "failed", finished_at=now(),
                   stdout_sha256=digest(stdout_path), stderr_sha256=digest(stderr_path))
        persist()
        assert code == 0, "Inspect the original command log: " + str(stderr_path)
        return stdout_path.read_text(), stderr_path.read_text()

    def probe(label, path, count=False):
        command = [FFPROBE, "-v", "error"]
        if count:
            command.append("-count_frames")
        command += ["-show_streams", "-show_format", "-of", "json", path]
        return json.loads(run(label, command)[0])

    def pcm_info(label, path, channels):
        value = probe(label, path)
        audio = [stream for stream in value["streams"] if stream["codec_type"] == "audio"]
        assert len(audio) == len(value["streams"]) == 1
        audio = audio[0]
        assert int(audio["sample_rate"]) == RATE and int(audio["channels"]) == channels
        assert audio["codec_name"].startswith("pcm_")
        count = Fraction(int(audio["duration_ts"])) * Fraction(audio["time_base"]) * RATE
        assert count.denominator == 1
        return int(count), value

    def master(label, source_audio, target, integrated, peak, lra):
        base = f"aresample={RATE},aformat=channel_layouts=stereo,apad,atrim=end_sample={samples}"
        norm = f"I={integrated}:TP={peak}:LRA={lra}"
        first = run(label + "-pass1", [FFMPEG, "-nostdin", "-hide_banner", "-i", source_audio,
                    "-map", "0:a:0", "-af", base + ",loudnorm=" + norm + ":print_format=json", "-f", "null", "-"])
        measured = loudness_json(first[1])
        filter2 = (base + ",loudnorm=" + norm + ":measured_I=" + measured["input_i"] +
                   ":measured_LRA=" + measured["input_lra"] + ":measured_TP=" + measured["input_tp"] +
                   ":measured_thresh=" + measured["input_thresh"] + ":offset=" + measured["target_offset"] +
                   f":linear=true:print_format=json,aresample={RATE},apad,atrim=end_sample={samples}")
        second = run(label + "-pass2", [FFMPEG, "-nostdin", "-n", "-hide_banner", "-i", source_audio,
                     "-map", "0:a:0", "-af", filter2, "-ar", str(RATE), "-ac", "2", "-c:a", "pcm_s24le", target])
        count, _ = pcm_info(label + "-probe", target, 2)
        assert count == samples
        return {"first_pass": measured, "second_pass": loudness_json(second[1]), "sha256": digest(target), "path": str(target)}

    def video_hash(label, path):
        result = run(label, [FFMPEG, "-nostdin", "-hide_banner", "-v", "error", "-i", path,
                            "-map", "0:v:0", "-c:v", "copy", "-f", "hash", "-hash", "sha256", "pipe:1"])[0].strip()
        assert re.fullmatch("SHA256=[0-9a-fA-F]{64}", result)
        return result.split("=", 1)[1].lower()

    persist()
    try:
        inventory = run("installed-voices", [SAY, "-v", "?"], timeout=30)[0]
        installed = [line for line in inventory.splitlines() if re.match(r"^Daniel\s+en_GB\s", line)]
        assert len(installed) == 1, "Daniel en_GB must already be installed; no voice download is attempted"
        report["voice"]["installed_inventory_line"] = installed[0]
        report["tool_versions"] = {
            "ffmpeg": run("ffmpeg-version", [FFMPEG, "-version"], timeout=30)[0].splitlines()[0],
            "ffprobe": run("ffprobe-version", [FFPROBE, "-version"], timeout=30)[0].splitlines()[0],
        }
        video_probe = probe("source-video-probe", paths["silent_video"])
        videos = [stream for stream in video_probe["streams"] if stream["codec_type"] == "video"]
        assert len(videos) == len(video_probe["streams"]) == 1
        original_video = videos[0]
        assert original_video["codec_name"] == "h264" and original_video["avg_frame_rate"] == "30/1"
        assert (original_video["width"], original_video["height"]) == (1920, 1080)
        assert int(original_video["nb_frames"]) == frames
        assert abs(float(original_video["duration"]) - duration) < 1e-5
        score_samples, score_probe = pcm_info("source-score-probe", paths["score_master"], 2)
        assert score_samples == samples
        report["source_video_probe"], report["source_score_probe"] = video_probe, score_probe

        bed = bytearray(samples * 2)
        for cue in cues:
            cue_dir = clips / cue["id"]
            cue_dir.mkdir()
            cue_record = {key: cue[key] for key in ("id", "start_ms", "window_end_ms", "intent", "focus_mode", "visual_focus", "resolved_visual_focus")}
            cue_record["attempts"] = []
            report["cues"].append(cue_record)
            available_samples = math.floor((cue["window_end_ms"] - cue["start_ms"] - plan["tail_guard_ms"]) * RATE / 1000)
            selected = None
            for variant, text in [("primary", cue["text"]), ("short", cue["short_text"])]:
                if variant == "short" and cue["short_text"] == cue["text"]:
                    continue
                rate = plan["preferred_rate_wpm"]
                tried = set()
                while rate not in tried:
                    tried.add(rate)
                    assert 145 <= rate <= 180
                    stem = f"{len(cue_record['attempts'])+1:02d}-{variant}-{rate}wpm"
                    text_path, aiff, wav = (cue_dir / (stem + suffix) for suffix in (".txt", ".aiff", ".wav"))
                    new_bytes(text_path, (text + "\n").encode())
                    assert not aiff.exists() and not wav.exists()
                    run("say-" + cue["id"] + "-" + stem, [SAY, "-v", "Daniel", "-r", str(rate), "-f", text_path, "-o", aiff], timeout=120)
                    aiff_probe = probe("aiff-" + cue["id"] + "-" + stem, aiff)
                    run("pcm-" + cue["id"] + "-" + stem, [FFMPEG, "-nostdin", "-n", "-hide_banner", "-v", "error", "-i", aiff,
                        "-map", "0:a:0", "-ar", str(RATE), "-ac", "1", "-c:a", "pcm_s16le", wav])
                    clip_samples, wav_probe = pcm_info("wav-" + cue["id"] + "-" + stem, wav, 1)
                    assert clip_samples > RATE // 2
                    attempt = {"variant": variant, "text": text, "word_count": word_count(text), "rate_wpm": rate,
                               "aiff": str(aiff), "aiff_sha256": digest(aiff), "wav": str(wav), "wav_sha256": digest(wav),
                               "text_sha256": digest(text_path), "samples": clip_samples, "duration_seconds": clip_samples / RATE,
                               "fits_window": clip_samples <= available_samples,
                               "aiff_probe": aiff_probe, "wav_probe": wav_probe}
                    cue_record["attempts"].append(attempt)
                    persist()
                    if clip_samples <= available_samples:
                        selected = attempt
                        break
                    if rate == 180:
                        break
                    # Only re-synthesise faster within the reviewed natural range.
                    # No sample stretching, truncating words, or generative rewrite.
                    rate = min(180, max(rate + 5, math.ceil(rate * clip_samples / available_samples) + 2))
                if selected:
                    break
            assert selected is not None, "Neither authored wording fits naturally: " + cue["id"]
            with wave.open(selected["wav"], "rb") as source_wav:
                assert source_wav.getparams()[:3] == (1, 2, RATE)
                values = array("h", source_wav.readframes(source_wav.getnframes()))
            if sys.byteorder != "little":
                values.byteswap()
            assert len(values) == selected["samples"]
            # Tiny edge fades remove PCM discontinuities; clip duration is intact.
            fade_in, fade_out = int(RATE * 0.005), int(RATE * 0.020)
            for index in range(min(fade_in, len(values))):
                values[index] = round(values[index] * index / fade_in)
            for index in range(min(fade_out, len(values))):
                values[-1-index] = round(values[-1-index] * index / fade_out)
            if sys.byteorder != "little":
                values.byteswap()
            start_sample = round(cue["start_ms"] * RATE / 1000)
            raw = values.tobytes()
            assert start_sample + selected["samples"] <= samples
            bed[start_sample * 2:start_sample * 2 + len(raw)] = raw
            cue_record.update(selected={key: selected[key] for key in ("variant", "text", "word_count", "rate_wpm", "aiff", "aiff_sha256", "wav", "wav_sha256", "samples", "duration_seconds")},
                              actual_end_ms=(start_sample + selected["samples"]) * 1000 / RATE,
                              remaining_window_ms=cue["window_end_ms"] - (start_sample + selected["samples"]) * 1000 / RATE,
                              fade_in_ms=5, fade_out_ms=20)
            assert cue_record["remaining_window_ms"] >= plan["tail_guard_ms"] - 1 / RATE * 1000
            persist()
            print(json.dumps({"stage": "voice-cue", "id": cue["id"], "rate_wpm": selected["rate_wpm"],
                              "seconds": selected["duration_seconds"], "window_fits": True}), flush=True)

        selected_words = sum(cue["selected"]["word_count"] for cue in report["cues"])
        assert selected_words <= plan["max_words"]
        report["spoken_word_count"] = selected_words
        report["spoken_audio_seconds"] = sum(cue["selected"]["duration_seconds"] for cue in report["cues"])
        report["music_only_seconds"] = duration - report["spoken_audio_seconds"]
        voice_bed = out_dir / "narration-raw-48k.wav"
        with wave.open(str(voice_bed), "wb") as output_wav:
            output_wav.setnchannels(1)
            output_wav.setsampwidth(2)
            output_wav.setframerate(RATE)
            output_wav.writeframes(bed)
        count, _ = pcm_info("voice-bed-probe", voice_bed, 1)
        assert count == samples
        mix = plan["mix"]
        voice_master = out_dir / "narration-master-48k.wav"
        report["voice_master"] = master("voice-normalize", voice_bed, voice_master,
            mix["voice_integrated_lufs"], mix["voice_true_peak_dbtp"], mix["voice_lra_lu"])
        # Recheck the normalised bed itself. This detects unexpected speech
        # outside the allocated windows after resampling/mastering.
        silence_log = run("voice-window-verification", [FFMPEG, "-nostdin", "-hide_banner", "-i", voice_master,
            "-map", "0:a:0", "-af", "silencedetect=noise=-50dB:d=0.02", "-f", "null", "-"])[1]
        activity, active_start = [], 0.0
        for kind, value in re.findall(r"silence_(start|end):\s*([0-9.eE+-]+)", silence_log):
            point = float(value)
            if kind == "start":
                if active_start is not None and point > active_start:
                    activity.append([active_start, point])
                active_start = None
            else:
                active_start = point
        if active_start is not None and active_start < duration - 1 / RATE:
            activity.append([active_start, duration])
        assert activity
        hits = {cue["id"]: 0 for cue in report["cues"]}
        for start, end in activity:
            matches = [cue for cue in report["cues"]
                       if start >= cue["start_ms"] / 1000 - 0.04 and end <= cue["window_end_ms"] / 1000 + 0.04]
            assert len(matches) == 1, "Mastered voice escaped its timing window: " + str([start, end])
            hits[matches[0]["id"]] += 1
        assert all(hits.values()), "A mastered voice cue is silent"
        report["voice_window_verification"] = {"threshold_db": -50, "silence_min_seconds": 0.02,
            "boundary_tolerance_seconds": 0.04, "active_intervals_seconds": activity, "non_silent_intervals_per_cue": hits}
        duck = make_duck_expression(report["cues"], mix)
        report["duck_expression"] = duck
        mix_filter = (
            f"[0:a:0]aresample={RATE},apad,atrim=end_sample={samples},asetpts=PTS-STARTPTS,"
            f"volume='{duck}':eval=frame[music];"
            f"[1:a:0]aresample={RATE},atrim=end_sample={samples},asetpts=PTS-STARTPTS[voice];"
            f"[music][voice]amix=inputs=2:duration=first:dropout_transition=0:normalize=0,"
            f"aresample={RATE},apad,atrim=end_sample={samples}[mix]")
        new_bytes(out_dir / "mix-filter.txt", (mix_filter + "\n").encode())
        mixed = out_dir / "narrated-mix-premaster-48k.wav"
        run("mix-score-and-voice", [FFMPEG, "-nostdin", "-n", "-hide_banner", "-i", paths["score_master"], "-i", voice_master,
            "-filter_complex", mix_filter, "-map", "[mix]", "-ar", str(RATE), "-ac", "2", "-c:a", "pcm_f32le", mixed])
        mixed_count, _ = pcm_info("premaster-probe", mixed, 2)
        assert mixed_count == samples
        final_master = out_dir / "narrated-master-48k.wav"
        report["final_master"] = master("final-normalize", mixed, final_master,
            mix["final_integrated_lufs"], mix["pcm_true_peak_dbtp"], mix["final_lra_lu"])
        run("mux-narrated-film", [FFMPEG, "-nostdin", "-n", "-hide_banner", "-v", "error",
            "-i", paths["silent_video"], "-i", final_master, "-map", "0:v:0", "-map", "1:a:0",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", str(RATE), "-ac", "2",
            "-t", format(duration, ".9f"), "-map_metadata", "-1", "-metadata", "title=CasePath — Every step has a reason",
            "-movflags", "+faststart", output])
        final_probe = probe("narrated-film-probe", output, count=True)
        videos = [stream for stream in final_probe["streams"] if stream["codec_type"] == "video"]
        audios = [stream for stream in final_probe["streams"] if stream["codec_type"] == "audio"]
        assert len(videos) == len(audios) == 1 and len(final_probe["streams"]) == 2
        final_video, final_audio = videos[0], audios[0]
        assert final_video["codec_name"] == "h264" and final_video["avg_frame_rate"] == "30/1"
        assert (final_video["width"], final_video["height"]) == (1920, 1080)
        assert int(final_video["nb_frames"]) == int(final_video["nb_read_frames"]) == frames
        assert abs(float(final_video["duration"]) - duration) < 1e-5
        assert final_audio["codec_name"] == "aac" and int(final_audio["channels"]) == 2 and int(final_audio["sample_rate"]) == RATE
        assert abs(float(final_audio.get("start_time", 0))) <= 1 / RATE + 1e-6
        assert abs(float(final_audio["duration"]) - duration) <= 1024 / RATE + 0.001
        hashes = {"source": video_hash("source-video-packets", paths["silent_video"]), "output": video_hash("narrated-video-packets", output)}
        assert hashes["source"] == hashes["output"], "Video packets changed"
        run("full-narrated-decode", [FFMPEG, "-nostdin", "-hide_banner", "-v", "error", "-xerror", "-i", output,
                                   "-map", "0:v:0", "-map", "0:a:0", "-f", "null", "-"], timeout=600)
        final_stats = loudness_json(run("final-aac-loudness", [FFMPEG, "-nostdin", "-hide_banner", "-i", output,
            "-map", "0:a:0", "-af", f"loudnorm=I={mix['final_integrated_lufs']}:TP={mix['final_true_peak_ceiling_dbtp']}:LRA={mix['final_lra_lu']}:print_format=json",
            "-f", "null", "-"])[1])
        assert abs(float(final_stats["input_i"]) - mix["final_integrated_lufs"]) <= 0.5
        assert float(final_stats["input_tp"]) <= mix["final_true_peak_ceiling_dbtp"]
        for name, path in paths.items():
            assert digest(path) == inputs["files"][name]["sha256"], "Input changed: " + name
        assert digest(input_path) == args.inputs_sha256
        assert digest(source_binding_path) == source_binding_sha
        assert digest(scored_original) == media["output_sha256"]
        assert digest(__file__) == report["helper_sha256"]
        new_bytes(out_dir / "narration-plan.json", paths["plan"].read_bytes())
        new_bytes(out_dir / "input-bindings.json", input_path.read_bytes())
        new_bytes(out_dir / "render_documentary_narration.py", Path(__file__).read_bytes())
        new_bytes(out_dir / "cue-timings.json", (json.dumps(report["cues"], indent=2) + "\n").encode())
        subtitles = out_dir / "CasePath_Documentary_Narrated.srt"
        new_bytes(subtitles, srt_for_cues(report["cues"]).encode("utf-8"))
        report["subtitles"] = {"path": str(subtitles), "sha256": digest(subtitles), "format": "srt",
                               "cues": len(report["cues"]), "wording": "actual selected authored clips",
                               "timings": "actual rendered clip starts and ends", "burned_into_video": False}
        report.update(status="passed", passed=True, finished_at=now(), originals_unchanged=True,
                      output_sha256=digest(output), output_bytes=output.stat().st_size,
                      encoded_video_sha256=hashes, output_probe=final_probe, final_aac_measurement=final_stats,
                      measured_integrated_lufs=float(final_stats["input_i"]), measured_true_peak_dbtp=float(final_stats["input_tp"]),
                      verification="All authored clips fit their declared cue windows; spotlight clips wait for visible arrival; video packets match; full decode and measured loudness passed; SRT uses actual selected clips. No subjective listening claim.")
        persist()
        print(json.dumps({"status": "passed", "output": str(output), "receipt": str(receipt_path),
                          "words": selected_words, "spoken_seconds": report["spoken_audio_seconds"],
                          "video_packets_unchanged": True, "lufs": report["measured_integrated_lufs"],
                          "subjective_listening_claimed": False}), flush=True)
        return 0
    except BaseException as error:
        stop_child()
        report.update(status="failed_requires_reconciliation", passed=False, finished_at=now(), error=repr(error))
        persist()
        print(json.dumps({"status": report["status"], "receipt": str(receipt_path), "error": repr(error)}), flush=True)
        raise
    finally:
        stop_child()


if __name__ == "__main__":
    raise SystemExit(main())
