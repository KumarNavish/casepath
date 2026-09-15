"""Concurrent materialization of the same file must not corrupt itself.

Both writers here write to a content-addressed destination, so two threads or two processes materializing
the same asset at once is normal rather than exceptional. They previously shared one temporary filename,
so a second writer overwrote the first writer's bytes mid-write and the first writer then failed its own
read-back check with a misleading "materialization failed". The payload below is large enough that the
writes genuinely interleave, and the barrier makes every thread start at once.
"""
from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from casepath_api.native_inference_v1 import SourcePrefixAssembler, sha256_bytes
from casepath_api.native_live_workspace_v1 import NativeLiveWorkspaceError, _atomic_write

THREADS = 12
PAYLOAD = bytes(range(256)) * 16_384          # 4 MiB, big enough for writes to overlap
OTHER = bytes(range(255, -1, -1)) * 16_384


def _race(target, path: Path, raw: bytes) -> list:
    """Run `target(path, raw)` from THREADS threads released simultaneously."""
    barrier = threading.Barrier(THREADS)

    def once():
        barrier.wait()
        try:
            target(path, raw)
            return None
        except BaseException as exc:  # returned, not raised, so every thread is accounted for
            return exc

    with ThreadPoolExecutor(max_workers=THREADS) as pool:
        return [f.result() for f in [pool.submit(once) for _ in range(THREADS)]]


def _temp_leftovers(directory: Path) -> list[Path]:
    return [p for p in directory.iterdir() if p.name.endswith(".tmp")]


@pytest.mark.parametrize(
    "target",
    [SourcePrefixAssembler._write_exact, _atomic_write],
    ids=["native_asset", "workspace_runtime_file"],
)
def test_concurrent_writers_of_the_same_bytes_all_succeed(tmp_path, target):
    destination = tmp_path / "3f2a.bin"

    failures = [exc for exc in _race(target, destination, PAYLOAD) if exc is not None]

    assert failures == [], f"concurrent writers failed: {failures[:3]}"
    assert destination.read_bytes() == PAYLOAD
    assert sha256_bytes(destination.read_bytes()) == sha256_bytes(PAYLOAD)
    assert _temp_leftovers(tmp_path) == []


@pytest.mark.parametrize(
    "target,error",
    [(SourcePrefixAssembler._write_exact, ValueError), (_atomic_write, NativeLiveWorkspaceError)],
    ids=["native_asset", "workspace_runtime_file"],
)
def test_different_bytes_at_the_same_path_are_still_rejected(tmp_path, target, error):
    destination = tmp_path / "3f2a.bin"
    target(destination, PAYLOAD)

    with pytest.raises(error):
        target(destination, OTHER)

    assert destination.read_bytes() == PAYLOAD, "a rejected write must not disturb the admitted bytes"
    assert _temp_leftovers(tmp_path) == []


@pytest.mark.parametrize(
    "target",
    [SourcePrefixAssembler._write_exact, _atomic_write],
    ids=["native_asset", "workspace_runtime_file"],
)
def test_a_failed_rename_leaves_no_temporary_behind(tmp_path, monkeypatch, target):
    destination = tmp_path / "3f2a.bin"

    def explode(self, other):
        raise OSError("rename refused")

    monkeypatch.setattr(Path, "replace", explode)

    with pytest.raises(OSError):
        target(destination, PAYLOAD)

    assert not destination.exists()
    assert _temp_leftovers(tmp_path) == []


@pytest.mark.parametrize(
    "target",
    [SourcePrefixAssembler._write_exact, _atomic_write],
    ids=["native_asset", "workspace_runtime_file"],
)
def test_writing_identical_bytes_twice_is_a_no_op(tmp_path, target):
    destination = tmp_path / "3f2a.bin"
    target(destination, PAYLOAD)
    first = destination.stat().st_ino

    target(destination, PAYLOAD)

    assert destination.stat().st_ino == first, "the second write should short-circuit, not replace"
    assert destination.read_bytes() == PAYLOAD
