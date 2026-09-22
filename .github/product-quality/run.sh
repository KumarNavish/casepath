#!/usr/bin/env bash
# Disposable product QA only: no provider, deployment, benchmark scoring or push.
set -euo pipefail
out="$RUNNER_TEMP/product-quality"
mkdir -p "$out"
git rev-parse HEAD > "$out/commit.txt"
exec > >(tee "$out/execution.log") 2>&1
python3 -m pip install --disable-pip-version-check 'uv==0.10.0'
./bin/casepath prepare
npm ci --prefix casepath-qa --ignore-scripts
(cd casepath-qa && npx playwright install --with-deps chromium)
# Keep a portable copy of the admitted interpreter and packages for the same
# source's local design loop. No data root, credentials or browser profile.
mkdir -p "$RUNNER_TEMP/qa-runtime"
python_root="$(.runtime/casepath-dev-v2/venv/bin/python -c 'import sys; print(sys.base_prefix)')"
cp -a "$python_root" "$RUNNER_TEMP/qa-runtime/python"
cp -a .runtime/casepath-dev-v2/venv "$RUNNER_TEMP/qa-runtime/venv"
tar -czf "$out/runtime.tar.gz" -C "$RUNNER_TEMP/qa-runtime" python venv
./bin/casepath dev > "$out/server.log" 2>&1 &
server=$!
trap 'kill -INT "$server" 2>/dev/null || true; wait "$server" 2>/dev/null || true' EXIT
for attempt in $(seq 1 120); do
  if curl --fail --silent http://127.0.0.1:4173/healthz >/dev/null; then break; fi
  if ! kill -0 "$server" 2>/dev/null; then cat "$out/server.log"; exit 1; fi
  sleep 1
done
# Resolve Playwright from the repository's locked dependency tree.
cp .github/product-quality/browser.mjs casepath-qa/.product-quality-browser.mjs
node casepath-qa/.product-quality-browser.mjs "$out"
rm casepath-qa/.product-quality-browser.mjs
