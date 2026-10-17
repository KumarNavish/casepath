#!/usr/bin/env bash
set -u
cd /workspace/casepath-release-ae0-shard4 || exit 97
git rev-parse HEAD > /workspace/knowledge-read-warm-20261016/review/e/retirement-6b3-source-pre.txt
git status --porcelain=v1 >> /workspace/knowledge-read-warm-20261016/review/e/retirement-6b3-source-pre.txt
sha256sum casepath-api/casepath_api/hosted_sql_v1.py casepath-api/casepath_api/hosted_storage_v1.py casepath-api/tests/test_hosted_snapshot_transport_v1.py casepath-api/tests/test_hosted_knowledge_warm_proof_v1.py >> /workspace/knowledge-read-warm-20261016/review/e/retirement-6b3-source-pre.txt
df -B1 /workspace > /workspace/knowledge-read-warm-20261016/review/e/retirement-6b3-disk-pre.txt
env HOME=/workspace/knowledge-read-warm-20261016/review/h-retirement TMPDIR=/workspace/knowledge-read-warm-20261016/review/t-retirement TMP=/workspace/knowledge-read-warm-20261016/review/t-retirement TEMP=/workspace/knowledge-read-warm-20261016/review/t-retirement PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/workspace/casepath-release-ae0-shard4/casepath-api:/workspace/casepath-release-ae0-shard4/casepath-api/tests /workspace/casepath-release-ae0-shard6/.runtime/casepath-dev-v2/venv/bin/python -m pytest -p no:cacheprovider -q casepath-api/tests/test_hosted_snapshot_transport_v1.py casepath-api/tests/test_hosted_knowledge_warm_proof_v1.py::test_raw_payload_reads_retire_http_sockets_while_compact_proofs_keep_pool casepath-api/tests/test_hosted_knowledge_warm_proof_v1.py::test_raw_source_sqlite_fallback_receives_no_http_keyword --basetemp=/workspace/knowledge-read-warm-20261016/review/t-retirement/pytest --junitxml=/workspace/knowledge-read-warm-20261016/review/e/retirement-6b3-independent.xml > /workspace/knowledge-read-warm-20261016/review/e/retirement-6b3-independent.log 2>&1
result=$?
printf '%s\n' "$result" > /workspace/knowledge-read-warm-20261016/review/e/retirement-6b3-exit.txt
git rev-parse HEAD > /workspace/knowledge-read-warm-20261016/review/e/retirement-6b3-source-post.txt
git status --porcelain=v1 >> /workspace/knowledge-read-warm-20261016/review/e/retirement-6b3-source-post.txt
sha256sum casepath-api/casepath_api/hosted_sql_v1.py casepath-api/casepath_api/hosted_storage_v1.py casepath-api/tests/test_hosted_snapshot_transport_v1.py casepath-api/tests/test_hosted_knowledge_warm_proof_v1.py >> /workspace/knowledge-read-warm-20261016/review/e/retirement-6b3-source-post.txt
df -B1 /workspace > /workspace/knowledge-read-warm-20261016/review/e/retirement-6b3-disk-post.txt
du -sb /workspace/knowledge-read-warm-20261016/review/h-retirement /workspace/knowledge-read-warm-20261016/review/t-retirement > /workspace/knowledge-read-warm-20261016/review/e/retirement-6b3-scratch.txt
cat /workspace/knowledge-read-warm-20261016/review/e/retirement-6b3-independent.log
cat /workspace/knowledge-read-warm-20261016/review/e/retirement-6b3-scratch.txt
exit "$result"
