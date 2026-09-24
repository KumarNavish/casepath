"""Deterministic content identities used by benchmark and run receipts."""

from __future__ import annotations

import ast
import hashlib
import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def digest_json(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def digest_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest_paths(root: Path, paths: list[Path]) -> str:
    """Hash relative path names and bytes, independent of filesystem timestamps."""

    digest = hashlib.sha256()
    for path in sorted(paths, key=lambda item: item.relative_to(root).as_posix()):
        relative = path.relative_to(root).as_posix().encode("utf-8")
        data = path.read_bytes()
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return digest.hexdigest()


def local_python_import_closure(
    root: Path,
    roots: Iterable[str],
    *,
    allowed_top_level: frozenset[str] | None = None,
) -> tuple[str, ...]:
    """Return the deterministic repository-local import closure of Python roots."""

    module_files: dict[str, str] = {}
    for scanned_path in root.rglob("*.py"):
        scanned_relative = scanned_path.relative_to(root)
        if any(part.startswith(".") for part in scanned_relative.parts):
            continue
        if allowed_top_level is not None and scanned_relative.parts[0] not in allowed_top_level:
            continue
        parts = list(scanned_relative.with_suffix("").parts)
        if parts[-1] == "__init__":
            parts.pop()
        if parts:
            module_files[".".join(parts)] = scanned_relative.as_posix()

    pending = list(dict.fromkeys(roots))
    included: set[str] = set()
    while pending:
        relative_path = pending.pop()
        if relative_path in included or not relative_path.endswith(".py"):
            continue
        path = root / relative_path
        if not path.is_file():
            raise ValueError(f"local import root is missing: {relative_path}")
        included.add(relative_path)
        module_parts = list(Path(relative_path).with_suffix("").parts)
        is_package = module_parts[-1] == "__init__"
        if is_package:
            module_parts.pop()
        current_package = module_parts if is_package else module_parts[:-1]
        for depth in range(1, len(module_parts)):
            init_path = "/".join(module_parts[:depth]) + "/__init__.py"
            if (root / init_path).is_file():
                pending.append(init_path)
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative_path)
        imported_modules: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    keep = len(current_package) - (node.level - 1)
                    if keep < 0:
                        continue
                    base_parts = current_package[:keep]
                    if node.module:
                        base_parts.extend(node.module.split("."))
                    base = ".".join(base_parts)
                else:
                    base = node.module or ""
                if base:
                    imported_modules.add(base)
                    imported_modules.update(
                        f"{base}.{alias.name}" for alias in node.names if alias.name != "*"
                    )
        for module in imported_modules:
            candidate = module
            while candidate:
                local = module_files.get(candidate)
                if local is not None:
                    pending.append(local)
                    break
                candidate = candidate.rpartition(".")[0]
    return tuple(sorted(included))
