#!/usr/bin/env python3
"""Create the static frontend deployment identity without editing authored assets."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any


REPOSITORY = Path(__file__).resolve().parents[2]
RELEASE_PATH = REPOSITORY / "casepath" / "release.json"
DEFAULT_OUTPUT = REPOSITORY / "casepath" / "deployment.json"
SOURCE_DATE_EPOCH = int(os.environ.get("SOURCE_DATE_EPOCH", "1786406400"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalized_commit(environment: Mapping[str, str]) -> tuple[str, str]:
    for variable in ("RENDER_GIT_COMMIT", "CASEPATH_SOURCE_COMMIT"):
        candidate = environment.get(variable, "").strip().lower()
        if re.fullmatch(r"[0-9a-f]{40}", candidate):
            return candidate, variable
    return "unknown", "unavailable_or_invalid"


def build_payload(environment: Mapping[str, str]) -> dict[str, Any]:
    release = json.loads(RELEASE_PATH.read_text(encoding="utf-8"))
    source_commit, source = normalized_commit(environment)
    frontend = release["components"]["frontend"]
    return {
        "alignment_eligible": source_commit != "unknown",
        "component": "frontend",
        "component_contract": frontend["contract"],
        "component_version": frontend["version"],
        "contract": "casepath.deployment-identity/1.0.0",
        "release_contract_sha256": sha256_file(RELEASE_PATH),
        "release_id": release["release_id"],
        "service": release["services"]["frontend"],
        "source_commit": source_commit,
        "source_commit_source": source,
        "unknown_semantics": "unknown never satisfies cross-service release alignment",
    }


def write_payload(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)
    os.utime(path, (SOURCE_DATE_EPOCH, SOURCE_DATE_EPOCH))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--require-known-commit",
        action="store_true",
        help="Fail when neither RENDER_GIT_COMMIT nor CASEPATH_SOURCE_COMMIT is valid.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output = args.output if args.output.is_absolute() else Path.cwd() / args.output
    payload = build_payload(os.environ)
    write_payload(output, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    if args.require_known_commit and not payload["alignment_eligible"]:
        print(
            "frontend deployment identity is unknown; refusing an alignable release build",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
