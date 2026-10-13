#!/bin/bash
set -eu
label="$1"
pattern="$2"
cd /workspace/casepath-operation-count-repair-20261013
exec env HOME=/workspace/casepath-smooth-layout-20261013-evidence/browser-qa/home TMPDIR=/workspace/bq-tmp TMP=/workspace/bq-tmp TEMP=/workspace/bq-tmp CASEPATH_PRIOR_ASSESSMENT_FIXTURE=/workspace/casepath-smooth-layout-20261013-evidence/layout/current-prior-fixture.json CASEPATH_REFERENCE_FIXTURE=/workspace/casepath-reference-polish-native-qa-evidence-20261013/native-fresh-reference.json CASEPATH_REFERENCE_MIGRATION_FIXTURE=/workspace/casepath-reference-polish-evidence-20261013/native-v1-v2-reference.json CASEPATH_BROWSER_JS_ASSET=/workspace/casepath-smooth-layout-20261013-evidence/browser-qa/assets/final.js CASEPATH_BROWSER_CSS_ASSET=/workspace/casepath-smooth-layout-20261013-evidence/browser-qa/assets/final.css CASEPATH_FOCUSED_RECEIPTS="/workspace/casepath-smooth-layout-20261013-evidence/browser-qa/$label" CASEPATH_BROWSER_DIAGNOSTICS="/workspace/casepath-smooth-layout-20261013-evidence/browser-qa/$label" CASEPATH_RECEIPTS_JSON_ONLY=1 node --test --test-reporter=tap --test-name-pattern="$pattern" casepath-qa/unified-product-browser-v1.test.cjs
