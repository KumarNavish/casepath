#!/usr/bin/env python3
"""Media-only edit of supplied native, variable-rate screenshots; offline by design.

Default: metadata-only plan. Encoding requires --encode and a complete v5 capture.
The source commit identifies the captured product, never this renderer branch.
No capture, browser automation, network requests, optical flow, or UI reconstruction.
"""
import argparse
import bisect
import collections
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time

W, H, FPS, GUTTER = 1920, 1080, 30, 64
CAPTION_SIZE = 42
MIN_ZOOM, MAX_SPEED, ENDCARD = 1.4, 6.0, 5.0
END_TEXT = ["CasePath · Evidence into action", "Synthetic claims · recorded replay"]
BG, INK = (239, 242, 236), (24, 61, 51)
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
REQUIRED_SAMPLE_FIELDS = (
    "activeStepRect", "excerptRect", "exactSpanRect", "factRect", "readheadRect",
    "railRect", "transportRect", "facts", "documents", "state", "operation",
)


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def stamp(value):
    value = float(value)
    require(math.isfinite(value), "Nonfinite capture timestamp")
    return value / 1000 if value > 1e11 else value


def rect(value):
    if not isinstance(value, dict):
        return None
    x = float(value.get("x", value.get("left", 0)))
    y = float(value.get("y", value.get("top", 0)))
    w = float(value.get("width", value.get("w", 0)))
    h = float(value.get("height", value.get("h", 0)))
    require(all(math.isfinite(v) for v in (x, y, w, h)), "Nonfinite geometry")
    return (x, y, w, h) if w > 0 and h > 0 else None


def union(rectangles):
    rectangles = [r for r in rectangles if r]
    if not rectangles:
        return None
    left = min(r[0] for r in rectangles)
    top = min(r[1] for r in rectangles)
    right = max(r[0] + r[2] for r in rectangles)
    bottom = max(r[1] + r[3] for r in rectangles)
    return left, top, right - left, bottom - top


def merged(windows, start, end):
    out = []
    for a, b in sorted((max(start, a), min(end, b)) for a, b in windows):
        if b <= a:
            continue
        if out and a <= out[-1][1]:
            out[-1][1] = max(b, out[-1][1])
        else:
            out.append([a, b])
    return out


def contains(window, t):
    return window[0] <= t <= window[1]


def work_identity(items, fact=False):
    """Order-independent work identity; captured rectangles never define work."""
    if items is None:
        return ()
    keys = ("id", "operation", "source_id", "sourceId") + (("text",) if fact else ())
    values = items if isinstance(items, list) else [items]
    stable = [{key: item.get(key) for key in keys} if isinstance(item, dict) else item
              for item in values]
    return tuple(sorted(json.dumps(item, sort_keys=True, separators=(",", ":")) for item in stable))


def fit_camera(cw, ch, bounds, desired=MIN_ZOOM, preferred=None):
    """CSS-coordinate crop; never discard the complete required pixel union.

    A required rectangle outside the captured viewport is an input failure, not
    permission to clip it. No header or whole-map constraint is added here.
    """
    if bounds is None:
        return (cw / 2, ch / 2, 1.0), None
    x, y, w, h = bounds
    require(x >= -.01 and y >= -.01 and x + w <= cw + .01 and y + h <= ch + .01,
            "Required excerpt/destination extends outside the captured viewport")
    # Padding is editorial; the original full union remains mandatory.
    left, top = max(0, x - 10), max(0, y - 10)
    right, bottom = min(cw, x + w + 10), min(ch, y + h + 10)
    bound = min(cw / (right - left), ch / (bottom - top))
    zoom = min(desired, bound)
    crop_w, crop_h = cw / zoom, ch / zoom
    px, py = preferred if preferred else ((left + right) / 2, (top + bottom) / 2)
    min_x, max_x = max(crop_w / 2, right - crop_w / 2), min(cw - crop_w / 2, left + crop_w / 2)
    min_y, max_y = max(crop_h / 2, bottom - crop_h / 2), min(ch - crop_h / 2, top + crop_h / 2)
    cx, cy = min(max(px, min_x), max_x), min(max(py, min_y), max_y)
    return (cx, cy, zoom), bound


class Movie:
    def __init__(self, args):
        self.args, self.root = args, args.input.resolve().parent
        self.raw = json.loads(args.input.read_text())
        self.commit = self.raw.get("source_commit")
        require(self.commit == args.source_commit,
                "capture.source_commit must exactly match explicit --source-commit")
        self.frames = self.raw.get("frames", [])
        self.samples = self.raw.get("samples", [])
        self.events = self.raw.get("events", [])
        require(2 <= len(self.frames) <= 10000 and self.samples, "Need actual frames and samples")
        self.ft = [stamp(f["t"]) for f in self.frames]
        self.st = [stamp(s["t"]) for s in self.samples]
        self.et = [stamp(e["t"]) for e in self.events]
        require(all(b > a for a, b in zip(self.ft, self.ft[1:])), "Frame times must strictly increase")
        require(self.st == sorted(self.st) and self.et == sorted(self.et), "Samples/events must be chronological")
        viewport = self.raw.get("viewport", {})
        css = viewport.get("css", viewport)
        self.cw, self.ch = float(css["width"]), float(css["height"])
        self.dpr = float(viewport.get("deviceScaleFactor", viewport.get("deviceScale", 0)))
        require(min(self.cw, self.ch, self.dpr) > 0, "Need CSS viewport and deviceScaleFactor/deviceScale")
        self.paths = []
        for frame in self.frames:
            relative = Path(frame["file"])
            require(not relative.is_absolute() and ".." not in relative.parts, "Frame must stay inside input root")
            path = self.root / relative
            require(path.resolve().is_relative_to(self.root), "Frame path escapes input root")
            self.paths.append(path)
        self.cache, self.fonts = collections.OrderedDict(), {}
        self.issues = []
        self.compat = args.compatibility_v4
        if not self.compat:
            for i, sample in enumerate(self.samples):
                missing = sorted(set(REQUIRED_SAMPLE_FIELDS) - sample.keys())
                require(not missing, f"Sample {i} lacks required capture fields: {missing}")
        self.start = max(self.ft[0], next((t for t, e in zip(self.et, self.events)
                                         if e.get("type") == "film-start"), self.ft[0]))
        self.end = self.ft[-1]
        require(self.start < self.end, "No captured interval after film-start")
        self.final_times = [t for t, s in zip(self.st, self.samples)
                            if str(s.get("state", "")).lower() in ("complete", "completed", "final")]
        self.final_times += [t for t, e in zip(self.et, self.events)
                             if e.get("type") in ("final", "film-result", "decision-final")]
        self.final_visible = any(self.start <= t <= self.end for t in self.final_times)
        self.native_final_visible = self.final_visible
        self.final_still, self.final_declaration = None, None
        if args.final_still_declaration:
            declaration = json.loads(args.final_still_declaration.read_text())
            relative = Path(declaration['file'])
            require(not relative.is_absolute() and '..' not in relative.parts, 'Final still must stay inside capture root')
            path = self.root / relative
            require(path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(self.root), 'Missing/linked final still')
            require(declaration['source_commit'] == self.commit and declaration['capture_json_sha256'] == digest(args.input), 'Final still capture binding mismatch')
            require(digest(path) == declaration['sha256'], 'Final still hash mismatch')
            after, before = declaration['captured_after_event'], declaration['captured_before_event']
            require(after['type'] == 'film-result' and before['type'] == 'film-end' and self.end < after['t'] < before['t'], 'Final still capture interval mismatch')
            require(after in self.events or any(e['type'] == after['type'] and e['t'] == after['t'] for e in self.events), 'Missing final result event')
            require(any(e['type'] == before['type'] and e['t'] == before['t'] for e in self.events), 'Missing film end event')
            from PIL import Image
            with Image.open(path) as image:
                require(image.size == (declaration['width'], declaration['height']), 'Final still dimensions mismatch')
                self.final_still = image.convert('RGB')
            self.final_declaration = declaration
            self.final_visible = True
        if not self.final_visible:
            self.issues.append("No final-state timestamp at or before the last actual frame; final hold/encoding blocked")
        self.build_plan()

    def sample(self, t):
        return self.samples[max(0, bisect.bisect_right(self.st, t) - 1)]

    @staticmethod
    def event_text(event):
        return " ".join(str(event.get(k, "")) for k in ("type", "role", "target", "operation")).lower()

    def active(self, sample):
        return any(rect(sample.get(k)) for k in ("readheadRect", "exactSpanRect", "factRect"))

    def build_plan(self):
        protected, full, self.labels, self.inspections = [], [], [], []
        prior_documents, prior_facts = None, None
        for i, (t, sample) in enumerate(zip(self.st, self.samples)):
            next_t = self.st[i + 1] if i + 1 < len(self.st) else self.end
            if self.active(sample):
                protected.append((t - .15, next_t + .15))
                label = "Connect the fact" if rect(sample.get("factRect")) else "Read the evidence"
                self.labels.append((t, next_t, label))
            documents = work_identity(sample.get("documents", sample.get("checkedSlots")))
            if prior_documents is not None and documents != prior_documents:
                protected.append((t - .8, next_t + .8))
                self.labels.append((t - .2, t + 1, "Check the document"))
            prior_documents = documents
            facts = work_identity(sample.get("facts"), fact=True)
            if prior_facts is not None and facts != prior_facts:
                protected.append((t - .8, next_t + .8))
                self.labels.append((t - .2, t + 1, "Connect the fact"))
            prior_facts = facts
            operation = str(sample.get("operation", "")).lower()
            if any(k in operation for k in ("extract", "bind", "attach", "land", "check", "decision")):
                protected.append((t - .15, next_t + .15))
            if sample.get("dialog") or str(sample.get("state", "")).lower() in ("paused", "inspect", "inspecting"):
                full.append((t - .25, next_t + .25))
                protected.append((t - .25, next_t + .25))
            if "decision" in operation or str(sample.get("state", "")).lower() in ("complete", "completed", "final", "decision"):
                full.append((t - .4, next_t + .4))
                protected.append((t - .4, next_t + .4))
        inspection_start, last_pointer = None, None
        for t, event in zip(self.et, self.events):
            text = self.event_text(event)
            if event.get("type") in ("click", "native-click"):
                protected.append((t - .8, t + .8))
                full.append((t - .8, t + .8))
            if ("inspection-start" in text or "inspect-source" in text or
                    event.get("type") in ("hold", "hold-start", "inspection-held")):
                inspection_start = t if inspection_start is None else min(inspection_start, t)
                self.labels.append((t, t + 2, "Inspect the source"))
            if event.get("type") == "hold" and event.get("duration") is not None:
                hold_end = t + float(event["duration"])
                require(math.isfinite(hold_end) and hold_end >= t, "Invalid logged hold duration")
                protected.append((t, hold_end))
                full.append((t, hold_end))
            if "resume" in text:
                if inspection_start is not None:
                    protected.append((inspection_start - .4, t + .8))
                    full.append((inspection_start - .6, t + .8))
                    self.inspections.append([inspection_start, t])
                    inspection_start = None
                self.labels.append((t, t + 1.2, "Resume the check"))
            if all(isinstance(event.get(k), (int, float)) for k in ("x", "y")):
                point = float(event["x"]), float(event["y"])
                if last_pointer is not None and point != last_pointer[1]:
                    # Preserve genuine logged travel; never interpolate a pointer.
                    protected.append((last_pointer[0] - .1, t + .1))
                    full.append((last_pointer[0] - .25, t + .25))
                last_pointer = t, point
            if event.get("type") in ("final", "film-result", "decision", "decision-final"):
                protected.append((t - .8, t + 1.2))
                full.append((t - .8, self.end))
        if inspection_start is not None:
            protected.append((inspection_start - .4, self.end))
            full.append((inspection_start - .6, self.end))
            self.issues.append("Source inspection has no logged resume; review supplied capture")
        protected += [(self.start, self.start + .8), (self.end - 1, self.end)]
        full += [(self.start, self.start + .5), (self.end - 1, self.end)]
        self.protected = merged(protected, self.start, self.end)
        self.full = merged(full, self.start, self.end)
        # Piecewise exact 1x in protected intervals; only routine gaps compress.
        edges = sorted({self.start, self.end, *(x for pair in self.protected for x in pair)})
        segments = [(a, b, any(contains(win, (a + b) / 2) for win in self.protected))
                    for a, b in zip(edges, edges[1:])]
        protected_seconds = sum(b - a for a, b, yes in segments if yes)
        routine_seconds = self.end - self.start - protected_seconds
        available = self.args.duration - ENDCARD
        minimum = protected_seconds + routine_seconds / MAX_SPEED
        self.feasible = minimum <= available + 1e-6
        if not self.feasible:
            self.issues.append(f"1x protected motion requires at least {minimum + ENDCARD:.3f}s including endcard")
        self.speed = 1.0 if self.end - self.start <= available else min(
            MAX_SPEED, routine_seconds / max(1e-12, available - protected_seconds))
        if available <= protected_seconds:
            self.speed = MAX_SPEED
        self.segments, out_t = [], 0.0
        for a, b, is_protected in segments:
            speed = 1.0 if is_protected else self.speed
            next_t = out_t + (b - a) / speed
            self.segments.append({"source": [a, b], "output": [out_t, next_t],
                                  "speed": speed, "protected": is_protected})
            out_t = next_t
        self.ui_duration = out_t
        # The separately supplied completed UI screenshot is an editorial hold,
        # never inserted into the native frame sequence or assigned a fake clock.
        self.hold = max(0.0, self.args.duration - ENDCARD - out_t) if self.final_visible else 0.0
        self.duration = out_t + self.hold + ENDCARD
        self.output_ends = [s["output"][1] for s in self.segments]

    def input_time(self, out_t):
        if out_t >= self.ui_duration:
            return self.end
        segment = self.segments[min(len(self.segments) - 1, bisect.bisect_right(self.output_ends, out_t))]
        return segment["source"][0] + (out_t - segment["output"][0]) * segment["speed"]

    def frame_index(self, source_t):
        return max(0, min(len(self.ft) - 1, bisect.bisect_right(self.ft, source_t) - 1))

    def camera_geometry(self, t):
        sample = self.sample(t)
        if any(contains(win, t) for win in self.full):
            return None, "full-ui"
        if not self.active(sample):
            return None, "context"
        excerpt = rect(sample.get("excerptRect"))
        destination = rect(sample.get("activeStepRect")) or rect(sample.get("destinationRect"))
        if self.compat:
            excerpt = excerpt or rect(sample.get("sourceRect"))
            destination = destination or rect(sample.get("railRect"))
        if not excerpt or not destination:
            return None, "missing-excerpt-or-destination"
        bounds = union([excerpt, destination, rect(sample.get("factRect")),
                        rect(sample.get("exactSpanRect")), rect(sample.get("readheadRect"))])
        if bounds[0] < 0 or bounds[1] < 0 or bounds[0] + bounds[2] > self.cw or bounds[1] + bounds[3] > self.ch:
            return None, 'native-pan-transition-full-ui'
        return bounds, "active"

    def camera(self, t, prior=None):
        bounds, mode = self.camera_geometry(t)
        if bounds is None:
            return (self.cw / 2, self.ch / 2, 1.0), None, mode
        preferred = None
        if prior:
            # A single editorial camera eases its position at output 30fps.
            goal = (bounds[0] + bounds[2] / 2, bounds[1] + bounds[3] / 2)
            q = 1 - math.exp(-6 / FPS)
            preferred = prior[0] + q * (goal[0] - prior[0]), prior[1] + q * (goal[1] - prior[1])
        fitted, bound = fit_camera(self.cw, self.ch, bounds, preferred=preferred)
        # Start the close-up just above the genuine working card. The viewport's
        # title/reused-version header stays entirely outside this body close-up.
        # A lower crop may be shorter than the viewport; render without stretching.
        cx, cy, zoom = fitted
        crop_h = self.ch / zoom
        cy = max(cy, bounds[1] - 14 + crop_h / 2)
        fitted = cx, cy, zoom
        return fitted, bound, mode

    def plan(self):
        camera_rows, missing = [], 0
        for t in self.st:
            if not self.start <= t <= self.end:
                continue
            camera, bound, mode = self.camera(t)
            if mode == "missing-excerpt-or-destination":
                missing += 1
            camera_rows.append({"t": t, "mode": mode, "center_css": list(camera[:2]), "zoom": camera[2],
                                "maximum_zoom_preserving_required_union": bound,
                                "meets_1_4": camera[2] >= MIN_ZOOM - 1e-9 if mode == "active" else None})
        if missing:
            self.issues.append(f"{missing} active samples lack complete excerpt/destination geometry")
        bounds_limited = [r for r in camera_rows if r["mode"] == "active" and not r["meets_1_4"]]
        if bounds_limited:
            self.issues.append(f"{len(bounds_limited)} active samples cannot fit required union at 1.4x; truthful lower bound reported")
        transitions = sum(r['mode'] == 'native-pan-transition-full-ui' for r in camera_rows)
        if transitions:
            self.issues.append(f'{transitions} transient native pan samples kept full UI because part of destination is outside original viewport; no missing pixels reconstructed')
        return {
            "status": "V4_COMPATIBILITY_ONLY_NOT_V5_ACCEPTANCE" if self.compat else "V5_METADATA_PLAN_ONLY_NOT_MEDIA_ACCEPTANCE",
            "source_commit": self.commit, "capture_index_sha256": digest(self.args.input),
            "raw_frame_files_read": False, "input_frame_count": len(self.frames),
            "viewport_css": [self.cw, self.ch], "device_scale": self.dpr,
            "native_frame_rate": "variable; actual source timestamps retained",
            "output": {"width": W, "height": H, "fps": FPS, "audio": False,
                       "selection": "duplicate preceding actual native frame; no interpolated UI or pointer motion"},
            "source_range": [self.start, self.end], "target_seconds": self.args.duration,
            "planned_seconds": self.duration, "target_feasible_preserving_1x": self.feasible,
            "ui_seconds": self.ui_duration, "routine_speed": self.speed,
            "editorial_final_image_hold_seconds": self.hold, "final_hold_rule": "Declared actual completed UI still held to requested target; native timeline unchanged",
            "final_visible_in_native_frames": self.native_final_visible,
            "separately_declared_actual_final_still": self.final_declaration,
            "endcard_seconds": ENDCARD, "endcard": END_TEXT,
            "protected_source_windows_1x": self.protected, "full_ui_source_windows": self.full,
            "logged_inspection_through_resume_windows": self.inspections,
            "segments": self.segments, "caption_gutter_pixels": GUTTER,
            "caption_font_pixels": CAPTION_SIZE,
            "captions": self.labels, "camera_samples": camera_rows,
            "camera_rule": "Complete excerpt plus actual destination and moving fact; no whole header/map lock during active work. Full UI on inspection, native pointer travel/clicks, decision and final.",
            "cursor_rule": "Only supplied actual logged x/y positions; no generated travel or click glow",
            "issues": self.issues,
            "not_verified": ["publication/source identity beyond supplied receipt", "actual source pixels and complete final state", "encoded video and rendered framing"],
        }

    def read_frame(self, source_t):
        from PIL import Image
        index = self.frame_index(source_t)
        if index not in self.cache:
            with Image.open(self.paths[index]) as image:
                expected = (round(self.cw * self.dpr), round(self.ch * self.dpr))
                require(image.size == expected, f"Frame {index} size {image.size} differs from viewport/deviceScale {expected}")
                self.cache[index] = image.convert("RGB")
            while len(self.cache) > 4:
                self.cache.popitem(last=False)
        self.cache.move_to_end(index)
        return self.cache[index]

    def cursor(self, t):
        for event in reversed(self.events[:bisect.bisect_right(self.et, t)]):
            if all(isinstance(event.get(k), (int, float)) for k in ("x", "y")):
                x, y = float(event["x"]), float(event["y"])
                require(math.isfinite(x) and math.isfinite(y), "Nonfinite cursor position")
                return x, y
        return None

    def render_frame(self, out_t, prior):
        from PIL import Image, ImageDraw, ImageFont
        def font(size):
            if size not in self.fonts:
                self.fonts[size] = ImageFont.truetype(self.args.font, size)
            return self.fonts[size]
        image = Image.new("RGB", (W, H), BG)
        draw = ImageDraw.Draw(image)
        if out_t >= self.ui_duration + self.hold:
            for text, y, size in zip(END_TEXT, (446, 540), (58, 29)):
                draw.text((W / 2, y), text, fill=INK, font=font(size), anchor="mt")
            return image, prior
        source_t = self.input_time(out_t)
        editorial_hold = out_t >= self.ui_duration and self.final_still is not None
        source = self.final_still if editorial_hold else self.read_frame(source_t)
        camera, _, _ = ((self.cw / 2, self.ch / 2, 1), None, 'actual-final-still') if editorial_hold else self.camera(source_t, prior)
        cx, cy, zoom = camera
        crop_w, crop_h = self.cw / zoom, self.ch / zoom
        x, y = max(0, cx - crop_w / 2), max(0, cy - crop_h / 2)
        crop_h = min(crop_h, self.ch - y)
        scale = min(W / crop_w, (H - GUTTER) / crop_h)
        width, height = round(crop_w * scale), round(crop_h * scale)
        left, top = (W - width) // 2, (H - GUTTER - height) // 2
        sx, sy = source.width / self.cw, source.height / self.ch
        box = (x * sx, y * sy, min(self.cw, x + crop_w) * sx, min(self.ch, y + crop_h) * sy)
        content = source.resize((width, height), Image.Resampling.LANCZOS, box=box)
        if not editorial_hold and self.args.cursor == "recorded" and not self.raw.get("cursor_in_frames", False):
            pointer = self.cursor(source_t)
            if pointer:
                px, py = (pointer[0] - x) * scale, (pointer[1] - y) * scale
                if 0 <= px < width and 0 <= py < height:
                    polygon = [(0, 0), (0, 23), (6, 17), (11, 27), (16, 25), (11, 15), (20, 15)]
                    # Draw inside the captured content only; never spill into captions.
                    ImageDraw.Draw(content).polygon([(px + a, py + b) for a, b in polygon],
                                                    fill=(250, 250, 248), outline=(25, 32, 29), width=2)
        image.paste(content, (left, top))
        if out_t < self.ui_duration:
            labels = [label for a, b, label in self.labels if a <= source_t <= b]
            if labels:
                caption = labels[-1]
                require(2 <= len(caption.split()) <= 4, "Caption must contain 2–4 words")
                draw.text((W / 2, H - GUTTER / 2), caption, fill=INK,
                          font=font(CAPTION_SIZE), anchor="mm")
        elif editorial_hold and out_t < self.ui_duration + 3:
            draw.text((W / 2, H - GUTTER / 2), 'Reach a decision', fill=INK,
                      font=font(CAPTION_SIZE), anchor='mm')
        return image, camera

    def encode(self, plan):
        require(not self.compat, "V4 compatibility input cannot encode as v5")
        require(self.feasible and self.final_visible and 45 <= self.duration <= 60,
                "Need a complete final capture fitting 45–60s while preserving protected 1x motion")
        require(not any("lack" in issue or "no logged resume" in issue for issue in self.issues),
                "Capture geometry/inspection receipt is incomplete")
        require(self.raw.get("error") in (None, "", False), "Capture reports an error")
        require(shutil.which("ffmpeg") and shutil.which("ffprobe"), "Existing ffmpeg/ffprobe required; no install attempted")
        require(Path(self.args.font).is_file(), "Existing local font required")
        total_bytes, manifest = 0, hashlib.sha256()
        for frame, path in zip(self.frames, self.paths):
            require(path.is_file() and not path.is_symlink(), "Missing or linked native frame")
            total_bytes += path.stat().st_size
            require(total_bytes <= 1536 * 1024**2, "Capture exceeds 1.5GiB bounded input")
            manifest.update(json.dumps([frame["file"], frame["t"], digest(path)], separators=(",", ":")).encode())
        require(shutil.disk_usage(self.args.output).free >= 200 * 1024**2, "Need 200MiB free for bounded video output")
        output = self.args.output / "CasePath-demo-agentic-v5.mp4"
        require(not output.exists(), "Refusing to overwrite an existing video")
        partial = self.args.output / "CasePath-demo-agentic-v5.partial.mp4"
        require(not partial.exists(), "Remove or inspect prior partial output before retry")
        command = ["ffmpeg", "-hide_banner", "-loglevel", "warning", "-nostdin", "-n", "-f", "rawvideo",
                   "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-an",
                   "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-threads", "2",
                   "-pix_fmt", "yuv420p", "-color_primaries", "bt709", "-color_trc", "bt709",
                   "-colorspace", "bt709", "-movflags", "+faststart", str(partial)]
        previous_handler = signal.getsignal(signal.SIGTERM)
        def cancel(_signal, _frame):
            raise KeyboardInterrupt("Media edit cancelled")
        signal.signal(signal.SIGTERM, cancel)
        started, process, prior = time.monotonic(), None, None
        try:
            with (self.args.output / "encode.log").open("w") as log:
                process = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=log)
                for n in range(math.ceil(self.duration * FPS - 1e-7)):
                    frame, prior = self.render_frame(n / FPS, prior)
                    process.stdin.write(frame.tobytes())
                    if n % FPS == 0 and partial.exists():
                        require(partial.stat().st_size < 100_000_000, "Video exceeds 100MB bounded output")
                process.stdin.close()
                require(process.wait(timeout=180) == 0, "ffmpeg failed; inspect encode.log")
            probe = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-show_format", "-show_streams",
                                                       "-of", "json", str(partial)]))
            streams = probe["streams"]
            require(len(streams) == 1, "Expected one video stream and no audio")
            video = streams[0]
            require((video["width"], video["height"], video["codec_name"], video["r_frame_rate"]) ==
                    (W, H, "h264", "30/1"), "Encoded format mismatch")
            require(45 <= float(probe["format"]["duration"]) <= 60 and partial.stat().st_size < 100_000_000,
                    "Encoded duration/size exceeds requested bounds")
            partial.rename(output)
            plan.update(status="ENCODED_FROM_SUPPLIED_V5_CAPTURE_REQUIRES_VISUAL_REVIEW", raw_frame_files_read=True,
                        input_manifest_sha256=manifest.hexdigest(), input_bytes=total_bytes,
                        output_sha256=digest(output), output_bytes=output.stat().st_size, ffprobe=probe,
                        encoding_seconds=time.monotonic() - started)
            plan["not_verified"] = ["publication/source identity beyond supplied receipt", "human review of encoded video"]
            (self.args.output / "edit-receipt.json").write_text(json.dumps(plan, indent=2) + "\n")
        except BaseException:
            if process is not None and process.poll() is None:
                process.kill()
                process.wait()
            partial.unlink(missing_ok=True)
            raise
        finally:
            signal.signal(signal.SIGTERM, previous_handler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Actual native capture.json; frames stay beside it")
    parser.add_argument("--source-commit", required=True, help="Actual captured product SHA, exactly 40 lowercase hex")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--duration", type=float, default=45, help="Target 45–60s including final hold and exact 5s endcard")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--plan-only", action="store_true", help="Metadata-only plan; also the default")
    mode.add_argument("--encode", action="store_true", help="Explicit future encode after receiving published v5 capture")
    parser.add_argument("--compatibility-v4", action="store_true", help="Old metadata math check only; disables encoding")
    parser.add_argument("--cursor", choices=("recorded", "none"), default="recorded")
    parser.add_argument("--font", default=FONT, help="Existing local font; no font download")
    parser.add_argument("--final-still-declaration", type=Path, help="Separate actual completed UI screenshot declaration; native capture stays unchanged")
    args = parser.parse_args()
    require(bool(re.fullmatch("[0-9a-f]{40}", args.source_commit)), "--source-commit must be actual 40 lowercase hex")
    require(math.isfinite(args.duration) and 45 <= args.duration <= 60, "Target must be 45–60s")
    require(not (args.compatibility_v4 and args.encode), "Compatibility metadata cannot encode")
    # Constrain every encoder subprocess HOME/TMP before starting it. No /tmp raw copies.
    runtime = Path(__file__).resolve().parent.parent
    for variable, directory in (("HOME", runtime / "h"), ("TMPDIR", runtime / "t"),
                                ("TMP", runtime / "t"), ("TEMP", runtime / "t")):
        directory.mkdir(parents=True, exist_ok=True)
        os.environ[variable] = str(directory)
    args.output.mkdir(parents=True, exist_ok=True)
    movie = Movie(args)
    plan = movie.plan()
    (args.output / "edit-plan.json").write_text(json.dumps(plan, indent=2) + "\n")
    print(json.dumps({"status": plan["status"], "planned_seconds": movie.duration,
                      "feasible": movie.feasible, "issues": movie.issues}), flush=True)
    if args.encode:
        movie.encode(plan)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, OSError, subprocess.SubprocessError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(2)
