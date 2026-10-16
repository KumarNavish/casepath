"""Execute the launcher's actual scratch lifetime in a disposable shell.

No product process, journal, environment, port or provider is used here.
"""
from __future__ import annotations

import os
from pathlib import Path
import signal
import subprocess
import time

import pytest


LAUNCHER = Path(__file__).resolve().parents[2] / "bin" / "casepath"


def startup(tmp_path: Path, *, capture_status: int = 0,
            journal_status: int = 0, allocation_failure: int = 0,
            serving: bool = False) -> subprocess.Popen[str]:
    source = LAUNCHER.read_text()
    start = source.index('\nruntime_closure_after_sync_path=') + 1
    end = source.index('# The controller itself is captured', start)
    body = source[start:end]
    scratch = tmp_path / "tmp"
    scratch.mkdir()
    (scratch / "unrelated").write_text("keep")
    data = tmp_path / "data"
    data.mkdir()
    (data / "casepath.db").write_text("protected sentinel")
    if allocation_failure:
        shim = tmp_path / "mktemp"
        shim.write_text(
            '#!/usr/bin/env bash\nset -eu\n'
            'count=0\n[[ ! -f "$0.count" ]] || count=$(cat "$0.count")\n'
            'count=$((count+1))\nprintf "%s" "$count" > "$0.count"\n'
            f'[[ "$count" != {allocation_failure} ]] || exit 42\n'
            'exec /usr/bin/mktemp "$@"\n'
        )
        shim.chmod(0o700)
        body = body.replace('/usr/bin/mktemp', f'"{shim}"')
    tail = 'exit 0\n'
    if serving:
        tail = (
            'sleep 300 &\nchild_pid=$!\n'
            'printf "%s" "$child_pid" > "$runtime_root/child"\n'
            'touch "$runtime_root/ready"\nwait "$child_pid"\n'
        )
    script = (
        'set -euo pipefail\n'
        'runtime_root="$1"\ndata_root="$1/data"\n'
        'legacy_data_root="$1/legacy"\nexecution_root="$1/source"\n'
        'child_pid=""\n'
        'capture_runtime_closure() { printf "inventory" > "$2"; '
        f'return {capture_status}; }}\n'
        f'validate_durable_journal() {{ return {journal_status}; }}\n'
        + body + tail
    )
    return subprocess.Popen(
        ['/bin/bash', '-c', script, 'scratch-test', str(tmp_path)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        start_new_session=True,
    )


def assert_preserved(tmp_path: Path) -> None:
    assert sorted(p.name for p in (tmp_path / 'tmp').iterdir()) == ['unrelated']
    assert (tmp_path / 'tmp/unrelated').read_text() == 'keep'
    assert (tmp_path / 'data/casepath.db').read_text() == 'protected sentinel'


@pytest.mark.parametrize(('capture_status', 'journal_status', 'expected'), [
    (0, 0, 0), (37, 0, 37), (0, 38, 38),
])
def test_scratch_cleanup_on_success_or_startup_failure(
    tmp_path: Path, capture_status: int, journal_status: int, expected: int,
) -> None:
    process = startup(tmp_path, capture_status=capture_status,
                      journal_status=journal_status)
    _, stderr = process.communicate(timeout=10)
    assert process.returncode == expected, stderr
    assert_preserved(tmp_path)


@pytest.mark.parametrize('allocation_failure', [1, 2, 3])
def test_scratch_cleanup_on_partial_allocation(
    tmp_path: Path, allocation_failure: int,
) -> None:
    process = startup(tmp_path, allocation_failure=allocation_failure)
    _, stderr = process.communicate(timeout=10)
    assert process.returncode == 42, stderr
    assert_preserved(tmp_path)


@pytest.mark.parametrize('interruption', [signal.SIGHUP, signal.SIGINT, signal.SIGTERM])
def test_interrupt_stops_owned_child_and_cleans_scratch(
    tmp_path: Path, interruption: int,
) -> None:
    process = startup(tmp_path, serving=True)
    try:
        deadline = time.monotonic() + 10
        while not (tmp_path / 'ready').exists():
            assert process.poll() is None, process.communicate()
            assert time.monotonic() < deadline
            time.sleep(0.01)
        child_pid = int((tmp_path / 'child').read_text())
        process.send_signal(interruption)
        _, stderr = process.communicate(timeout=10)
        assert process.returncode == 128 + interruption, stderr
        with pytest.raises(ProcessLookupError):
            os.kill(child_pid, 0)
        assert_preserved(tmp_path)
    finally:
        # Only the disposable session created by this test may be stopped.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait(timeout=10)
