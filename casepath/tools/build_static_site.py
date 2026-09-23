#!/usr/bin/env python3
"""Build the minimal public CasePath static site from an exact allowlist."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Optional

import build_deployment_identity as deployment_identity


REPOSITORY = Path(__file__).resolve().parents[2]
SOURCE_ROOT = REPOSITORY / "casepath"
DEFAULT_OUTPUT = REPOSITORY / "casepath-public"
OUTPUT_DIRECTORY_NAME = DEFAULT_OUTPUT.name

PUBLIC_ROOT_FILES = (
    "_headers",
    "index.html",
    "corpus.html",
    "method.html",
    "research.html",
    "release.json",
)
PUBLIC_ASSETS = (
    "assets/corpus.css",
    "assets/corpus.js",
    "assets/corpus-index.json",
    "assets/method-guide.css",
    "assets/research-evidence.css",
    "assets/paired-study-evidence.json",
    "assets/native-study-evidence.json",
    "assets/method-guide.js",
    "assets/method-guide-data.json",
    "assets/live-v16-viewer-fix.css",
    "assets/live-v16.css",
    "assets/live-v16.js",
    "assets/live-v16-stability.js",
    "assets/live-v17-continuity.css",
    "assets/live-v17.css",
    "assets/live-v17.js",
    "assets/live-v18.css",
    "assets/live-v18-handoff.js",
    "assets/live-v18-insertion-guard.js",
    "assets/live-v18-law-normalize.js",
    "assets/live-v18.js",
    "assets/live-v19-active-stage.js",
    "assets/live-v19.css",
    "assets/live-v20-focus.css",
    "assets/live-v20-focus.js",
    "assets/process-story.css",
    "assets/process-story.js",
    "assets/artifact-canvas.css",
    "assets/artifact-canvas.js",
    "assets/foundation-live.css",
    "assets/foundation-live.js",
    "assets/insurance-protocol-v1.css",
    "assets/insurance-protocol-v1.js",
    "assets/claims-workspace-v1.css",
    "assets/claims-workspace-v1.js",
    "assets/claims-workspace-presentation-v1.js",
    "assets/claims-workspace-presentation-v1.css",
    "assets/agent-work-v1.js",
    "assets/agent-work-v1.css",
    "assets/process-evidence-v2.css",
    "assets/process-evidence-v2.js",
)
GENERATED_FILES = ("deployment.json",)
PUBLIC_INVENTORY = frozenset((*PUBLIC_ROOT_FILES, *PUBLIC_ASSETS, *GENERATED_FILES))
PUBLIC_DIRECTORIES = frozenset({"assets"})
CONTENT_BOUND_ASSETS = (
    "assets/live-v16.css",
    "assets/live-v17.css",
    "assets/live-v17-continuity.css",
    "assets/live-v18.css",
    "assets/live-v19.css",
    "assets/live-v20-focus.css",
    "assets/insurance-protocol-v1.css",
    "assets/process-story.css",
    "assets/artifact-canvas.css",
    "assets/foundation-live.css",
    "assets/claims-workspace-v1.css",
    "assets/claims-workspace-v1.js",
    "assets/claims-workspace-presentation-v1.js",
    "assets/claims-workspace-presentation-v1.css",
    "assets/process-evidence-v2.css",
    "assets/process-evidence-v2.js",
    "assets/live-v16.js",
    "assets/live-v16-stability.js",
    "assets/live-v18-insertion-guard.js",
    "assets/live-v17.js",
    "assets/live-v18.js",
    "assets/live-v18-handoff.js",
    "assets/live-v19-active-stage.js",
    "assets/live-v20-focus.js",
    "assets/process-story.js",
    "assets/artifact-canvas.js",
    "assets/foundation-live.js",
    "assets/insurance-protocol-v1.js",
    "assets/agent-work-v1.js",
    "assets/agent-work-v1.css",
)
DYNAMIC_CONTENT_BOUND_ASSETS = {
    "assets/live-v16-viewer-fix.css": "assets/live-v16-stability.js",
    "assets/live-v18-law-normalize.js": "assets/live-v18-handoff.js",
    "assets/live-v19.css": "assets/live-v18-handoff.js",
}


class StaticSiteBuildError(RuntimeError):
    """Raised when the curated static site cannot be built safely."""


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _resolved_output(path: Path) -> Path:
    candidate = path.expanduser()
    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate
    if candidate.name != OUTPUT_DIRECTORY_NAME:
        raise StaticSiteBuildError(
            f"static build output must use the dedicated {OUTPUT_DIRECTORY_NAME!r} directory name"
        )
    if candidate.is_symlink():
        raise StaticSiteBuildError("static build output must not be a symlink")
    output = candidate.resolve()
    allowed_output = DEFAULT_OUTPUT.expanduser().resolve()
    if output != allowed_output:
        raise StaticSiteBuildError(
            f"static build output must be the repository-owned {allowed_output}"
        )
    source = SOURCE_ROOT.resolve()
    if _is_within(output, source) or _is_within(source, output):
        raise StaticSiteBuildError(
            "static build output must not contain or be contained by authored casepath source"
        )
    return output


def _validate_authored_sources() -> None:
    for relative_path in (*PUBLIC_ROOT_FILES, *PUBLIC_ASSETS):
        source = SOURCE_ROOT / relative_path
        if not source.is_file() or source.is_symlink():
            raise StaticSiteBuildError(
                f"curated public source must be a regular authored file: {relative_path}"
            )
    index = (SOURCE_ROOT / "index.html").read_text(encoding="utf-8")
    for relative_path in CONTENT_BOUND_ASSETS:
        digest = hashlib.sha256((SOURCE_ROOT / relative_path).read_bytes()).hexdigest()
        locator = f'{relative_path}?sha256={digest}'
        if index.count(relative_path) != 1 or index.count(locator) != 1:
            raise StaticSiteBuildError(
                "curated product asset has anything other than one exact byte-bound URL: "
                f"{relative_path}"
            )
    for relative_path, loader_path in DYNAMIC_CONTENT_BOUND_ASSETS.items():
        digest = hashlib.sha256((SOURCE_ROOT / relative_path).read_bytes()).hexdigest()
        locator = f"{relative_path}?sha256={digest}"
        loader = (SOURCE_ROOT / loader_path).read_text(encoding="utf-8")
        if loader.count(relative_path) != 1 or loader.count(locator) != 1:
            raise StaticSiteBuildError(
                "dynamic product asset has anything other than one exact byte-bound URL: "
                f"{relative_path}"
            )


def inventory(root: Path) -> tuple[frozenset[str], frozenset[str]]:
    files: set[str] = set()
    directories: set[str] = set()
    for path in root.rglob("*"):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            raise StaticSiteBuildError(
                f"curated public output must not contain symlinks: {relative}"
            )
        if path.is_dir():
            directories.add(relative)
        elif path.is_file():
            files.add(relative)
        else:
            raise StaticSiteBuildError(
                f"curated public output contains a non-regular entry: {relative}"
            )
    return frozenset(files), frozenset(directories)


def verify_inventory(root: Path) -> None:
    files, directories = inventory(root)
    if files != PUBLIC_INVENTORY or directories != PUBLIC_DIRECTORIES:
        unexpected = sorted(files - PUBLIC_INVENTORY)
        missing = sorted(PUBLIC_INVENTORY - files)
        raise StaticSiteBuildError(
            "curated public inventory mismatch; "
            f"missing={missing!r}, unexpected={unexpected!r}, "
            f"directories={sorted(directories)!r}"
        )


def build_static_site(
    output_path: Path,
    environment: Mapping[str, str],
    *,
    require_known_commit: bool = False,
) -> dict[str, Any]:
    """Build and atomically replace one exact public tree."""

    output = _resolved_output(output_path)
    payload = deployment_identity.build_payload(environment)
    if require_known_commit and not payload["alignment_eligible"]:
        raise StaticSiteBuildError(
            "frontend deployment identity is unknown; refusing an alignable release build"
        )
    _validate_authored_sources()

    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=f".{output.name}.build-", dir=str(output.parent))
    )
    previous: Optional[Path] = None
    try:
        for relative_path in (*PUBLIC_ROOT_FILES, *PUBLIC_ASSETS):
            source = SOURCE_ROOT / relative_path
            destination = staging / relative_path
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        deployment_identity.write_payload(staging / "deployment.json", payload)
        verify_inventory(staging)

        if output.exists() and not output.is_dir():
            raise StaticSiteBuildError(
                f"static build output exists but is not a regular directory: {output}"
            )
        if output.exists():
            previous = Path(
                tempfile.mkdtemp(
                    prefix=f".{output.name}.previous-", dir=str(output.parent)
                )
            )
            previous.rmdir()
            os.replace(output, previous)
        try:
            os.replace(staging, output)
        except Exception:
            if previous is not None and previous.exists() and not output.exists():
                os.replace(previous, output)
            raise
        if previous is not None:
            shutil.rmtree(previous)
    finally:
        if staging.exists():
            shutil.rmtree(staging)

    verify_inventory(output)
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--require-known-commit",
        action="store_true",
        help="Fail before publishing when no supported source commit is valid.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        payload = build_static_site(
            DEFAULT_OUTPUT,
            os.environ,
            require_known_commit=args.require_known_commit,
        )
    except StaticSiteBuildError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(
        json.dumps(
            {
                "file_count": len(PUBLIC_INVENTORY),
                "output": str(_resolved_output(DEFAULT_OUTPUT)),
                "release_id": payload["release_id"],
                "source_commit": payload["source_commit"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
