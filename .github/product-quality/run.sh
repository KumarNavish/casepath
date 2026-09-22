#!/usr/bin/env bash
# Disposable product QA only: no provider, deployment, benchmark scoring or push.
set -euo pipefail
export UV_LINK_MODE=copy
out="$RUNNER_TEMP/product-quality"
mkdir -p "$out"
git rev-parse HEAD > "$out/commit.txt"
exec > >(tee "$out/execution.log") 2>&1
python3 -m pip install --disable-pip-version-check 'uv==0.10.0'
./bin/casepath prepare
npm ci --prefix casepath-qa --ignore-scripts
(cd casepath-qa && npx playwright install --with-deps chromium)
./bin/casepath dev > "$out/server.log" 2>&1 &
server=$!
trap 'kill -INT "$server" 2>/dev/null || true; wait "$server" 2>/dev/null || true' EXIT
for attempt in $(seq 1 120); do
  if curl --fail --silent http://127.0.0.1:4173/healthz >/dev/null; then break; fi
  if ! kill -0 "$server" 2>/dev/null; then cat "$out/server.log"; exit 1; fi
  sleep 1
done
# Temporary module links live outside all sealed product roots. Never change
# casepath-qa after launch: startup admission checks the full source inventory.
ln -s "$GITHUB_WORKSPACE/casepath-qa/node_modules" .github/product-quality/node_modules
node .github/product-quality/browser.mjs "$out"
