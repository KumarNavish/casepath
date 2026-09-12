from __future__ import annotations

from collections.abc import Callable
import os
from pathlib import Path
import shutil
import stat

import pytest


def _regular_tree_snapshot(root: Path) -> tuple[tuple[str, str, int], ...]:
    root_metadata = root.lstat()
    if root.is_symlink() or not stat.S_ISDIR(root_metadata.st_mode):
        raise RuntimeError("test corpus root must be a regular directory")

    rows: list[tuple[str, str, int]] = []
    pending = [root]
    while pending:
        current = pending.pop()
        metadata = current.lstat()
        relative = "." if current == root else current.relative_to(root).as_posix()
        if current.is_symlink():
            raise RuntimeError(f"test corpus tree contains a symlink: {relative}")
        if stat.S_ISDIR(metadata.st_mode):
            rows.append((relative, "directory", stat.S_IMODE(metadata.st_mode)))
            with os.scandir(current) as entries:
                children = sorted((Path(entry.path) for entry in entries), reverse=True)
            pending.extend(children)
        elif stat.S_ISREG(metadata.st_mode):
            rows.append((relative, "file", stat.S_IMODE(metadata.st_mode)))
        else:
            raise RuntimeError(f"test corpus tree contains a special entry: {relative}")
    return tuple(sorted(rows))


def _copy_writable_regular_tree(source: Path, destination: Path) -> Path:
    source = Path(source)
    before = _regular_tree_snapshot(source)
    shutil.copytree(source, destination, symlinks=True)
    copied = _regular_tree_snapshot(destination)
    if tuple((path, kind) for path, kind, _ in copied) != tuple(
        (path, kind) for path, kind, _ in before
    ):
        raise RuntimeError("test corpus copy changed the source inventory")

    for relative, _, mode in copied:
        target = destination if relative == "." else destination / relative
        os.chmod(target, mode | stat.S_IWUSR, follow_symlinks=False)

    if _regular_tree_snapshot(source) != before:
        raise RuntimeError("test corpus copy changed immutable source modes")
    for relative, _, mode in _regular_tree_snapshot(destination):
        if not mode & stat.S_IWUSR:
            raise RuntimeError(f"test corpus copy is not owner-writable: {relative}")
    return destination


@pytest.fixture()
def writable_corpus_copy() -> Callable[[Path, Path], Path]:
    """Return a checked copier for mutation-only test fixtures."""

    return _copy_writable_regular_tree
