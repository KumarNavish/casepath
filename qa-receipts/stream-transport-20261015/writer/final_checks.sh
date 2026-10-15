#!/bin/bash
set -u
export TMPDIR=/workspace/cp-stream-transport-evidence-20261015/tmp
export TMP="$TMPDIR" TEMP="$TMPDIR"
export HOME=/workspace/cp-stream-transport-evidence-20261015/home
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH=/workspace/casepath-stream-transport-20261015/casepath-api
cd /workspace/casepath-stream-transport-20261015
sha256sum casepath-api/casepath_api/autonomous_api_v1.py casepath-api/tests/test_autonomous_operations_v1.py casepath-api/tests/test_operation_trace_storage_v1.py casepath/tools/sites_worker.mjs casepath-qa/sites-proxy.test.cjs > /workspace/cp-stream-transport-evidence-20261015/writer/final-start-source-sha256.txt
compgen -e | sort | rg 'PROXY|CA_BUNDLE|CERT|^OIC_|^TMP|^TEMP$|^HOME$|^PYTHON' > /workspace/cp-stream-transport-evidence-20261015/writer/inherited-binding-names-only.txt
/workspace/casepath-release-ae0-inventory/.runtime/casepath-dev-v2/venv/bin/python -m pytest -q -p no:cacheprovider --junitxml=/workspace/cp-stream-transport-evidence-20261015/writer/python-affected-final.junit.xml casepath-api/tests/test_autonomous_operations_v1.py -k operation_transport > /workspace/cp-stream-transport-evidence-20261015/writer/python-affected-final.log 2>&1
python_result=$?
/opt/codex/runtimes/codex-primary-runtime/dependencies/node/bin/node --test casepath-qa/sites-proxy.test.cjs > /workspace/cp-stream-transport-evidence-20261015/writer/node-final.log 2>&1
node_result=$?
sha256sum casepath-api/casepath_api/autonomous_api_v1.py casepath-api/tests/test_autonomous_operations_v1.py casepath-api/tests/test_operation_trace_storage_v1.py casepath/tools/sites_worker.mjs casepath-qa/sites-proxy.test.cjs > /workspace/cp-stream-transport-evidence-20261015/writer/final-end-source-sha256.txt
printf 'python_exit=%s\nnode_exit=%s\n' "$python_result" "$node_result" > /workspace/cp-stream-transport-evidence-20261015/writer/final-status.txt
cat /workspace/cp-stream-transport-evidence-20261015/writer/python-affected-final.log /workspace/cp-stream-transport-evidence-20261015/writer/node-final.log /workspace/cp-stream-transport-evidence-20261015/writer/final-status.txt
test "$python_result" -eq 0 && test "$node_result" -eq 0
