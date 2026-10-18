#!/usr/bin/env bash
set -u
cd /workspace/casepath-reference-85a-qa
export TMPDIR=/workspace/tt-tmp TMP=/workspace/tt-tmp TEMP=/workspace/tt-tmp
export NODE_PATH=/opt/codex/runtimes/codex-primary-runtime/dependencies/node/node_modules
export PLAYWRIGHT_EXECUTABLE_PATH="${PLAYWRIGHT_EXECUTABLE_PATH:-/usr/bin/chromium}"
export CASEPATH_REFERENCE_FIXTURE=/workspace/casepath-reference-polish-evidence-20261013/native-v1-v2-reference.json
export CASEPATH_KNOWLEDGE_FIXTURE=/workspace/knowledge-learning-coordinator-20261016/projection-6064.json
export CASEPATH_FOCUSED_RECEIPTS="/workspace/casepath-touch-targets-20261018/e/$1"
export CASEPATH_RECEIPTS_JSON_ONLY=1
mkdir -p "$CASEPATH_FOCUSED_RECEIPTS"
/opt/codex/runtimes/codex-primary-runtime/dependencies/node/bin/node --test --test-name-pattern="${CASEPATH_TOUCH_PATTERN:-^coarse touch targets:}" casepath-qa/unified-product-browser-v1.test.cjs > "/workspace/casepath-touch-targets-20261018/e/$1.tap" 2>&1
test_status=$?
printf '%s\n' "$test_status" > "/workspace/casepath-touch-targets-20261018/e/$1.exit"
tail -n 65 "/workspace/casepath-touch-targets-20261018/e/$1.tap"
exit "$test_status"
