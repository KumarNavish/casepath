#!/usr/bin/env bash
cd /workspace/casepath-operations-review-20261013 || exit
export TMPDIR=/workspace/owt TMP=/workspace/owt TEMP=/workspace/owt
export NODE_PATH=/opt/codex/runtimes/codex-primary-runtime/dependencies/node/node_modules
/opt/codex/runtimes/codex-primary-runtime/dependencies/node/bin/node --test --test-reporter=tap casepath-qa/autonomous-language-v1.test.cjs
