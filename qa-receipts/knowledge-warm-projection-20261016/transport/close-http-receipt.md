# Explicit read-only HTTP retirement

Host: `656813ef2295` (Cloud).
Checkout: `/workspace/casepath-release-ae0-shard5`.
Base: `7c2f36c027a266c87d6b3f1a54bd24931a7f1a64`.
Pushed commit: `e7d522c73b8b34ba928150cd061e00fab6f2d34c`.
Branch: `codex/knowledge-warm-transport-20261016`.

Only `casepath-api/casepath_api/hosted_sql_v1.py` and
`casepath-api/tests/test_hosted_snapshot_transport_v1.py` changed.
No app/storage/frontend edits, no generated seal, no dependencies, no service,
deployment, production credentials, native database or public product calls.

The new strict-boolean keyword `close_http=False` is exposed only by
`read_snapshot(queries, *, close_http=False)` and
`execute_read_once(sql, parameters=(), *, close_http=False)`.
Both reject non-bools before dispatch. True adds `Connection: close` to a local
per-request header dictionary. This retires the current HTTP/1.1 response's
socket after its body; it does not promise a fresh socket before that request,
mutate shared-client headers, close the shared client, or change defaults/writes.
All request/response bounds, deadlines, protocol checks, poisoning, connection
ownership and no-retry semantics remain unchanged.

Storage writer owns opt-in for cold journal raw pages and raw source pages.
Compact proof snapshots stay pooled by default. Mac owns the final native probe.
This change follows the Mac-reported 60-request raw-close diagnostic; no native
performance measurements were executed in Cloud.

## Verification

Failing-first command: exit 1; 21 expected failures (missing keyword API),
46 deselected; 0.35 seconds.

```bash
HOME=/workspace/knowledge-read-warm-20261016/transport/home TMPDIR=/workspace/knowledge-read-warm-20261016/transport/tmp TEMP=/workspace/knowledge-read-warm-20261016/transport/tmp PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/workspace/casepath-release-ae0-shard5/casepath-api:/workspace/casepath-release-ae0-shard5/casepath-api/tests /workspace/casepath-release-ae0-shard6/.runtime/casepath-dev-v2/venv/bin/python -m pytest -q casepath-api/tests/test_hosted_snapshot_transport_v1.py -k 'close_http or raw_close_header' --junitxml=/workspace/knowledge-read-warm-20261016/transport/artifacts/close-http-red.xml > /workspace/knowledge-read-warm-20261016/transport/artifacts/close-http-red.log 2>&1; result=$?; tail -32 /workspace/knowledge-read-warm-20261016/transport/artifacts/close-http-red.log; exit "$result"
```

Focused SQL/transport command: exit 0; 98 passed; 1.48 seconds.

```bash
HOME=/workspace/knowledge-read-warm-20261016/transport/home TMPDIR=/workspace/knowledge-read-warm-20261016/transport/tmp TEMP=/workspace/knowledge-read-warm-20261016/transport/tmp PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/workspace/casepath-release-ae0-shard5/casepath-api:/workspace/casepath-release-ae0-shard5/casepath-api/tests /workspace/casepath-release-ae0-shard6/.runtime/casepath-dev-v2/venv/bin/python -m pytest -q casepath-api/tests/test_hosted_snapshot_transport_v1.py casepath-api/tests/test_hosted_sql_v1.py --junitxml=/workspace/knowledge-read-warm-20261016/transport/artifacts/close-http-green.xml > /workspace/knowledge-read-warm-20261016/transport/artifacts/close-http-green.log 2>&1; result=$?; cat /workspace/knowledge-read-warm-20261016/transport/artifacts/close-http-green.log; exit "$result"
```

Coverage includes strict bool rejection, both helpers' True/default/False headers,
unchanged CREATE/INSERT headers, unchanged shared-client headers and ownership,
actual overlapping two-thread raw-close and compact snapshots with a barrier,
response byte/total-deadline guards, cancellation exception stream closure,
poisoning and no retries. Existing SQL tests also passed. `git diff --check`
passed. No full suite ran.

Source SHA-256:

```text
bc04fdabbb4dbe793668177c27e46080784113503c4c064cd231aba69df45fd9  casepath-api/casepath_api/hosted_sql_v1.py
ee4454e1fae99d172feab5ed2bf1c1f8c988a0bf33626e29030e477e4c6ddba5  casepath-api/tests/test_hosted_snapshot_transport_v1.py
```
