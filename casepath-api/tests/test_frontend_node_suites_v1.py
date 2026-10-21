"""Run the focused frontend Node suites as part of the deterministic gate.

The browser workspace has no Python renderer, so its copy, read-only preview,
knowledge-binding and motion invariants are only exercised by these suites.
Running them here makes ``./bin/casepath test`` fail when the frontend drifts
instead of leaving the drift to be found by hand.
"""

from __future__ import annotations

from functools import lru_cache
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
QA = REPOSITORY / "casepath-qa"
SUITE_TIMEOUT_SECONDS = 600
FAILURE_TAIL_LINES = 120
REQUIRE_VARIABLE = "CASEPATH_REQUIRE_FRONTEND_SUITES"

# (suite, needs Playwright Chromium)
SUITES = (
    ("autonomous-workspace-v1.test.cjs", False),
    ("autonomous-language-v1.test.cjs", False),
    ("sites-autonomous-entry.test.cjs", False),
    ("autonomous-evidence-identity-v2.test.cjs", True),
    ("unified-product-v1.test.cjs", False),
    ("autonomous-desk-v3.test.cjs", False),
    ("autonomous-cases-v4.test.cjs", False),
    ("autonomous-knowledge-w6.test.cjs", False),
    ("autonomous-northstar-v1.test.cjs", False),
    ("autonomous-presentation-v1.test.cjs", False),
    ("autonomous-presentation-browser-v1.test.cjs", True),
)

PLAYWRIGHT_PROBE = """
const fs = require('node:fs');
const {chromium} = require('playwright');
const configured = process.env.PLAYWRIGHT_EXECUTABLE_PATH;
const executable = configured || (fs.existsSync('/usr/bin/chromium') ? '/usr/bin/chromium' : chromium.executablePath());
if (!executable || !fs.existsSync(executable)) {
  process.stdout.write(`Playwright Chromium is not installed at ${executable || 'its default path'}`);
  process.exit(3);
}
"""


def _unavailable(reason: str) -> None:
    if os.environ.get(REQUIRE_VARIABLE) == "1":
        pytest.fail(f"{reason}; {REQUIRE_VARIABLE}=1 requires the frontend suites")
    pytest.skip(reason)


def _node_environment() -> dict[str, str]:
    # os.environ already carries PATH, NODE_PATH, PLAYWRIGHT_EXECUTABLE_PATH
    # and PLAYWRIGHT_BROWSERS_PATH when the caller sets them.
    environment = dict(os.environ)
    environment.setdefault("CASEPATH_PYTHON", sys.executable)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    return environment


@lru_cache(maxsize=1)
def _node() -> str | None:
    configured = os.environ.get("CASEPATH_NODE")
    if configured:
        return configured
    return shutil.which("node")


@lru_cache(maxsize=1)
def _playwright_problem(node: str) -> str | None:
    try:
        completed = subprocess.run(
            [node, "-e", PLAYWRIGHT_PROBE],
            cwd=QA,
            env=_node_environment(),
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return "the Playwright availability probe timed out"
    if completed.returncode == 0:
        return None
    if completed.returncode == 3:
        return completed.stdout.strip()
    return "the playwright module is not resolvable from casepath-qa (set NODE_PATH)"


def _tail(text: str) -> str:
    return "\n".join(text.splitlines()[-FAILURE_TAIL_LINES:])


@pytest.mark.parametrize(
    ("suite", "needs_browser"),
    SUITES,
    ids=[suite.removesuffix(".test.cjs") for suite, _ in SUITES],
)
def test_frontend_node_suite_passes(suite: str, needs_browser: bool) -> None:
    node = _node()
    if not node:
        _unavailable("node is not on PATH and CASEPATH_NODE is unset")
    assert Path(node).is_file() and os.access(node, os.X_OK), (
        f"configured node executable is unusable: {node}"
    )
    if needs_browser:
        problem = _playwright_problem(node)
        if problem:
            _unavailable(problem)

    path = QA / suite
    assert path.is_file(), f"focused frontend suite is missing: {path}"
    try:
        completed = subprocess.run(
            # Newer Node prints the spec reporter even when piped; the checks
            # below read TAP.
            [node, "--test", "--test-reporter=tap", str(path)],
            cwd=REPOSITORY,
            env=_node_environment(),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=SUITE_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        output = exc.output if isinstance(exc.output, str) else (exc.output or b"").decode(errors="replace")
        pytest.fail(f"{suite} exceeded {SUITE_TIMEOUT_SECONDS}s\n{_tail(output)}")

    failing = [line for line in completed.stdout.splitlines() if line.startswith("not ok ")]
    assert completed.returncode == 0, (
        f"{suite} exited {completed.returncode}; failing tests:\n"
        + ("\n".join(failing) or "(none reported)")
        + f"\n--- last {FAILURE_TAIL_LINES} lines ---\n{_tail(completed.stdout)}"
    )
    assert "# fail 0" in completed.stdout, _tail(completed.stdout)
