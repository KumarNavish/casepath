#!/usr/bin/env bash
# Re-check the paper's stored results from a git clone: data manifests, the product's parity hash, Study 3's
# analysis, post-hoc results, number macros and figures, the analysis tests, and the re-analysis of Studies 1 and 2.
# No model calls and no network. Nothing in the checkout is changed. One line per step; exit status 1 on any failure.
#
#   research/tmis2026/reproduce.sh [--keep] [--skip-latex]
#
# Needs: Python 3.10 or later with the packages in requirements-reproduce.txt (set PYTHON to choose the
# interpreter), git, tar, and the product commit in the clone:
#   git fetch origin claude/casepath-internal-paper-sync-20261110d
# See RELEASE.md.
set -euo pipefail
cd "$(dirname "$0")"
PY="${PYTHON:-python3}"
exec "$PY" release/reproduce.py "$@"
