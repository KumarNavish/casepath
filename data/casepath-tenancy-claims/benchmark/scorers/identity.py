"""One canonical content identity for the public CasePath evaluator."""

from __future__ import annotations

from pathlib import Path

from manifests.digests import digest_paths, local_python_import_closure


def scorer_code_paths(root: Path) -> tuple[Path, ...]:
    relative = local_python_import_closure(
        root,
        ("scorers/aggregate.py", "scorers/identity.py"),
        allowed_top_level=frozenset({"contracts", "manifests", "scorers"}),
    )
    return tuple(root / item for item in relative)


def scorer_code_sha256(root: Path) -> str:
    return digest_paths(root, list(scorer_code_paths(root)))


__all__ = ["scorer_code_paths", "scorer_code_sha256"]
