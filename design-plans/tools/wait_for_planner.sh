#!/bin/bash
# Blocks until the planner posts a new PR #21 comment (body starts with "PLANNER") after SINCE,
# prints every such comment in order, and exits 0. Run it whenever you are waiting for review.
# Usage: design-plans/tools/wait_for_planner.sh 2026-10-21T07:54:00Z   (UTC, ISO 8601)
set -euo pipefail
SINCE=${1:?usage: wait_for_planner.sh <ISO-UTC timestamp>}
while :; do
  out=$(gh api "repos/KumarNavish/casepath/issues/21/comments?since=$SINCE&per_page=100" \
    --jq ".[] | select(.created_at > \"$SINCE\") | select(.body | startswith(\"PLANNER\")) | \"=== \" + .created_at + \" \" + .html_url + \"\n\" + .body")
  if [ -n "$out" ]; then printf '%s\n' "$out"; exit 0; fi
  sleep 20
done
