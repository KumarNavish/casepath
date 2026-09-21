"""Immutable bytes, strict JSON and deterministic request identities."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
from typing import Any
from ..obligation_control_v1 import Invalid
from ..source_only_runtime_v1 import decode, digest, regular_bytes, hash_string


def canonical(obj: Any) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def immutable(path: Path, raw: bytes) -> str:
    """Exclusive durable publication; identical replay is read-only, never replace."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    except FileExistsError:
        if regular_bytes(path, max(len(raw), 1)) != raw:
            raise Invalid(f'immutable content conflict: {path.name}')
        return sha(raw)
    with os.fdopen(fd, 'wb') as f:
        f.write(raw); f.flush(); os.fsync(f.fileno())
    parent = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(parent)
    finally:
        os.close(parent)
    return sha(raw)


def save(path: Path, obj: Any) -> str:
    return immutable(path, canonical(obj) + b'\n')


def safe_member(root: Path, relative: str, prefixes: tuple[str, ...]) -> Path:
    """Explicit input allowlist; rejects symlink ancestors as well as final links."""
    from pathlib import PurePosixPath
    rel = PurePosixPath(relative)
    if not isinstance(relative, str) or rel.is_absolute() or '\\' in relative or any(p in {'..', '.'} for p in rel.parts):
        raise Invalid('unsafe input path')
    if not any(relative.startswith(p) for p in prefixes):
        raise Invalid('path is not an observable-input/source role')
    if any(p.lower() in {'gold', 'vault', 'sealed', 'targets', 'answers'} for p in rel.parts):
        raise Invalid('target/evaluator paths are outside producer authority')
    current = Path(root)
    if current.is_symlink():
        raise Invalid('symlink input root')
    for part in rel.parts:
        current /= part
        if current.is_symlink():
            raise Invalid('symlink input component')
    return current


def load(path: Path, limit: int = 16 * 1024 * 1024) -> Any:
    return decode(regular_bytes(Path(path), limit))
