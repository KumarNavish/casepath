#!/bin/bash
set -u
label="$1"
css="$2"
pattern="${3:-^causal formation native: settled stage dependency strokes stay inside}"
out="/workspace/casepath-edge-clearance-20261014-evidence/$label"
mkdir -p "$out"
cd /workspace/casepath-operations-review-20261013
env HOME=/workspace/ec-h TMPDIR=/workspace/ec-t TMP=/workspace/ec-t TEMP=/workspace/ec-t CASEPATH_REFERENCE_FIXTURE=/workspace/casepath-reference-polish-native-qa-evidence-20261013/native-fresh-reference.json CASEPATH_REFERENCE_MIGRATION_FIXTURE=/workspace/casepath-reference-polish-evidence-20261013/native-v1-v2-reference.json CASEPATH_PRIOR_ASSESSMENT_FIXTURE=/workspace/casepath-smooth-layout-20261013-evidence/layout/current-prior-fixture.json CASEPATH_BROWSER_CSS_ASSET="$css" CASEPATH_FOCUSED_RECEIPTS="$out" node --test --test-reporter=tap --test-name-pattern="$pattern" casepath-qa/unified-product-browser-v1.test.cjs > "$out/test.log" 2>&1
status=$?
printf '%s\n' "$status" > "$out/exit-status.txt"
tail -15 "$out/test.log"
exit "$status"
