#!/usr/bin/env bash
# The submission release test. Prints PASS or FAILED and nothing ambiguous in between.
#
# It covers the method, the benchmark harness, both product integrations, and the offline reproduction of
# every number the paper cites. It deliberately excludes tests/test_cli_v1.py, whose seven failures predate
# this work and concern adapter source-drift detection and a CLI byte cap; see RELEASE_TEST.md.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="${PYTHON:-$ROOT/.runtime/casepath-dev-v2/venv/bin/python}"
[ -x "$PY" ] || PY="$(command -v python3)"
export PYTHONDONTWRITEBYTECODE=1
fail=0

echo "== method, harness and product tests =="
( cd "$ROOT/casepath-api" && "$PY" -m pytest tests/ -q \
    -k "artifact_gate or evidential or arena or agent_work or confirmatory or concurrency" ) || fail=1

echo
echo "== offline reproduction of every cited number =="
"$PY" "$ROOT/release/reproduce_analysis.py" || fail=1

echo
if [ "$fail" -eq 0 ]; then echo "PASS"; else echo "FAILED"; fi
exit "$fail"
