#!/usr/bin/env python3
"""Build a ChatGPT Sites bundle from the curated CasePath public tree."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import tempfile

import build_static_site


REPOSITORY = Path(__file__).resolve().parents[2]
PUBLIC_ROOT = REPOSITORY / "casepath-public"
OUTPUT_ROOT = REPOSITORY / "dist"
WORKER_SOURCE = Path(__file__).with_name("sites_worker.mjs")
API_CONFIGURATION = "<script>window.CASEPATH_API = window.location.origin;</script>"
API_SCRIPT_MARKER = '<script src="assets/live-v16.js'


class SitesBuildError(RuntimeError):
    """Raised when a deployable Sites bundle cannot be built safely."""


def build() -> None:
    build_static_site.verify_inventory(PUBLIC_ROOT)
    if not WORKER_SOURCE.is_file() or WORKER_SOURCE.is_symlink():
        raise SitesBuildError("Sites worker source is missing or unsafe")

    staging = Path(tempfile.mkdtemp(prefix=".casepath-sites-", dir=REPOSITORY))
    previous: Path | None = None
    try:
        shutil.copytree(PUBLIC_ROOT, staging / "client")
        index_path = staging / "client" / "index.html"
        index_html = index_path.read_text(encoding="utf-8")
        if API_SCRIPT_MARKER not in index_html:
            raise SitesBuildError("CasePath entry point does not load live-v16.js")
        index_path.write_text(
            index_html.replace(
                API_SCRIPT_MARKER,
                f"{API_CONFIGURATION}\n  {API_SCRIPT_MARKER}",
                1,
            ),
            encoding="utf-8",
        )
        (staging / "server").mkdir(parents=True)
        shutil.copy2(WORKER_SOURCE, staging / "server" / "index.js")

        if OUTPUT_ROOT.exists():
            previous = Path(tempfile.mkdtemp(prefix=".casepath-sites-previous-", dir=REPOSITORY))
            previous.rmdir()
            os.replace(OUTPUT_ROOT, previous)
        try:
            os.replace(staging, OUTPUT_ROOT)
        except Exception:
            if previous is not None and previous.exists() and not OUTPUT_ROOT.exists():
                os.replace(previous, OUTPUT_ROOT)
            raise
        if previous is not None:
            shutil.rmtree(previous)
    finally:
        if staging.exists():
            shutil.rmtree(staging)

    build_static_site.verify_inventory(OUTPUT_ROOT / "client")
    if not (OUTPUT_ROOT / "server" / "index.js").is_file():
        raise SitesBuildError("Sites worker entry point was not built")


def main() -> int:
    try:
        build()
    except (SitesBuildError, build_static_site.StaticSiteBuildError) as exc:
        print(f"Sites build failed: {exc}")
        return 1
    print(f"Built CasePath Sites bundle at {OUTPUT_ROOT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
