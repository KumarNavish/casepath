#!/usr/bin/env bash
set -u
cd /workspace/casepath-reference-85a-qa
export TMPDIR=/workspace/mch-tmp TMP=/workspace/mch-tmp TEMP=/workspace/mch-tmp
export NODE_PATH=/opt/codex/runtimes/codex-primary-runtime/dependencies/node/node_modules
export CASEPATH_PYTHON=/workspace/.local/share/uv/python/cpython-3.13.9-linux-x86_64-gnu/bin/python
export PYTHONDONTWRITEBYTECODE=1
export PLAYWRIGHT_EXECUTABLE_PATH=/usr/bin/chromium
export CASEPATH_FOCUSED_RECEIPTS="/workspace/casepath-mobile-case-header-20261018/e/$1"
mkdir -p "$CASEPATH_FOCUSED_RECEIPTS"
/opt/codex/runtimes/codex-primary-runtime/dependencies/node/bin/node --test --test-name-pattern='^mobile case header:' casepath-qa/unified-product-browser-v1.test.cjs > "/workspace/casepath-mobile-case-header-20261018/e/$1.tap" 2>&1
test_status=$?
printf '%s\n' "$test_status" > "/workspace/casepath-mobile-case-header-20261018/e/$1.exit"
tail -n 85 "/workspace/casepath-mobile-case-header-20261018/e/$1.tap"
exit "$test_status"
