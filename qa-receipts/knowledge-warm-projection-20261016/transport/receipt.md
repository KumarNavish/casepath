# Hosted snapshot transport and read-only startup warmup

Host: `656813ef2295` (Cloud).
Checkout: `/workspace/casepath-release-ae0-shard5`.
Base: `39be4a080926f659d70d429db81410b74e4bd279`.
Initial pushed commit: `8d7af06883548027f1fc837f66c0039d29e6d584`.
Metadata/cleanup followup: `d826df1fd4278125ad254402bc1a178bd731d4a2`.
Final pushed commit: `7c2f36c027a266c87d6b3f1a54bd24931a7f1a64` (three commits from base).
Branch: `codex/knowledge-warm-transport-20261016`.

Four authored files only: `hosted_sql_v1.py`, `hosted_app_v1.py`,
`test_hosted_snapshot_transport_v1.py`, `test_public_hosted_read_only_v1.py`.
No generated seal, frontend, native fixture, dependencies, provider calls,
production credentials/database/API access, deployment, or service changes.
The integration owner owns the final source seal and native validation.

`read_snapshot` requires a fresh connection and 1..128 SELECT pairs; sends
BEGIN, each SELECT, COMMIT, and close in one Hrana pipeline; validates all
response entries and decoded results before returning tuple cursors; requires
terminal null baton and clean local transaction/cache state; poisons all SQL or
protocol/transport failures without retries. The request and response bound
remains 32 MiB, total deadline 12 seconds, SDK timeout 3/8/4/2 seconds.

`TursoDatabase(reuse_http=True)` owns one client (8 connections, 4 keepalive,
30-second expiry); each DB connection retains independent baton/cache/transaction.
Per-connection close borrows this pool explicitly. Existing injection/default
ownership stays unchanged. Only an internally created app database is closed by
app shutdown or failed startup. The app shuts dispatch, sets the store read-only,
then calls the complete `controller.knowledge.learning_view()` before exposing
state/readiness. The new warmup only reads; existing startup initialization is
unchanged. Failed warmup leaves health unavailable and cleans owned resources.

## Exact verification commands

All commands ran in `/workspace/casepath-release-ae0-shard5`, reusing clone6's
prepared pinned dependencies with this checkout on PYTHONPATH. HOME and temporary
paths were isolated below this task's transport directory.

Failing-first command (exit 1, 5 expected failures, 44 deselected, 5.29 seconds):

```bash
HOME=/workspace/knowledge-read-warm-20261016/transport/home TMPDIR=/workspace/knowledge-read-warm-20261016/transport/tmp TEMP=/workspace/knowledge-read-warm-20261016/transport/tmp PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/workspace/casepath-release-ae0-shard5/casepath-api:/workspace/casepath-release-ae0-shard5/casepath-api/tests /workspace/casepath-release-ae0-shard6/.runtime/casepath-dev-v2/venv/bin/python -m pytest -q casepath-api/tests/test_hosted_snapshot_transport_v1.py casepath-api/tests/test_public_hosted_read_only_v1.py -k 'snapshot_returns or reused_http or public_startup_verifies or readiness_is_closed or app_closes_only' --junitxml=/workspace/knowledge-read-warm-20261016/transport/artifacts/red.xml > /workspace/knowledge-read-warm-20261016/transport/artifacts/red.log 2>&1; result=$?; cat /workspace/knowledge-read-warm-20261016/transport/artifacts/red.log; exit "$result"
```

Initial implementation command (exit 0, 49 passed, 16.57 seconds):

```bash
HOME=/workspace/knowledge-read-warm-20261016/transport/home TMPDIR=/workspace/knowledge-read-warm-20261016/transport/tmp TEMP=/workspace/knowledge-read-warm-20261016/transport/tmp PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/workspace/casepath-release-ae0-shard5/casepath-api:/workspace/casepath-release-ae0-shard5/casepath-api/tests /workspace/casepath-release-ae0-shard6/.runtime/casepath-dev-v2/venv/bin/python -m pytest -q casepath-api/tests/test_hosted_snapshot_transport_v1.py casepath-api/tests/test_public_hosted_read_only_v1.py --junitxml=/workspace/knowledge-read-warm-20261016/transport/artifacts/green-initial.xml > /workspace/knowledge-read-warm-20261016/transport/artifacts/green-initial.log 2>&1; result=$?; cat /workspace/knowledge-read-warm-20261016/transport/artifacts/green-initial.log; exit "$result"
```

Focused regression command (exit 0, 99 passed, 25.21 seconds):

```bash
HOME=/workspace/knowledge-read-warm-20261016/transport/home TMPDIR=/workspace/knowledge-read-warm-20261016/transport/tmp TEMP=/workspace/knowledge-read-warm-20261016/transport/tmp PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/workspace/casepath-release-ae0-shard5/casepath-api:/workspace/casepath-release-ae0-shard5/casepath-api/tests /workspace/casepath-release-ae0-shard6/.runtime/casepath-dev-v2/venv/bin/python -m pytest -q casepath-api/tests/test_hosted_sql_v1.py casepath-api/tests/test_hosted_snapshot_transport_v1.py casepath-api/tests/test_public_hosted_read_only_v1.py casepath-api/tests/test_hosted_app_v1.py casepath-api/tests/test_hosted_proxy_v1.py casepath-api/tests/test_hosted_recovery_v1.py --junitxml=/workspace/knowledge-read-warm-20261016/transport/artifacts/focused.xml > /workspace/knowledge-read-warm-20261016/transport/artifacts/focused.log 2>&1; result=$?; cat /workspace/knowledge-read-warm-20261016/transport/artifacts/focused.log; exit "$result"
```

`git diff --check` passed. No complete suite or generated sealing was run,
per assigned scope. This tests local synthetic Hrana only and makes no native
latency claim. Storage writer owns the native read-only probe and compact proof
integration; Mac owns production-like validation.

## Initial commit source SHA-256

```text
428f7d36ce642fdf31e2df163b1e2b23d52164c13231acd193c472836b8b116d  casepath-api/casepath_api/hosted_sql_v1.py
bb94c8f76eeba44404fe3944b72ba65d02a8036deb19d8b10ef51219bd67cfc5  casepath-api/casepath_api/hosted_app_v1.py
349a7f05d6f44427ed6238de7ba88a747501e67d6e742c15eabab3eb388a4bd2  casepath-api/tests/test_hosted_snapshot_transport_v1.py
16beeef63ce4e7616cf8318fd99a9c5840369df5eecfb889684f6ce6e0af67ff  casepath-api/tests/test_public_hosted_read_only_v1.py
```

## Reviewed followup

`d826df1fd4278125ad254402bc1a178bd731d4a2` accepts valid retained
`last_insert_rowid` integer metadata on read-only statements (the original int64
decoder stays unchanged; affected-row counts remain zero and transaction
acknowledgements remain empty). A failing metadata test reproduced the excessive
restriction before the change. Failed-startup cleanup now attempts every owned
resource close and preserves the original startup failure even if controller
cleanup itself raises; its new test also failed before the fix.

Startup constructors perform no journal discovery. The explicit entry path is
`HostedAutonomousController.__init__` -> `AutonomousController.__init__` (knowledge
object/executor/locks only), `shutdown()`, `knowledge.learning_view()` ->
`AutonomousKnowledge._read(True)` -> `store.knowledge_snapshot()`. It does not
enter `list()`, `_read_summaries()`, `resume()`, or `wake_pending()`. The existing
warmup test was strengthened to fail if any of those paths runs during startup.
The model remains absent and warmup statements are read-only. Existing startup
schema initialization has not been added to or moved into warmup.

Metadata failing-first (exit 1, 1 expected failure, 44 deselected, 0.13 seconds):

```bash
HOME=/workspace/knowledge-read-warm-20261016/transport/home TMPDIR=/workspace/knowledge-read-warm-20261016/transport/tmp TEMP=/workspace/knowledge-read-warm-20261016/transport/tmp PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/workspace/casepath-release-ae0-shard5/casepath-api:/workspace/casepath-release-ae0-shard5/casepath-api/tests /workspace/casepath-release-ae0-shard6/.runtime/casepath-dev-v2/venv/bin/python -m pytest -q casepath-api/tests/test_hosted_snapshot_transport_v1.py -k retained_last_insert --junitxml=/workspace/knowledge-read-warm-20261016/transport/artifacts/metadata-red.xml > /workspace/knowledge-read-warm-20261016/transport/artifacts/metadata-red.log 2>&1; result=$?; cat /workspace/knowledge-read-warm-20261016/transport/artifacts/metadata-red.log; exit "$result"
```

Metadata transport regressions (exit 0, 45 passed, 0.22 seconds):

```bash
HOME=/workspace/knowledge-read-warm-20261016/transport/home TMPDIR=/workspace/knowledge-read-warm-20261016/transport/tmp TEMP=/workspace/knowledge-read-warm-20261016/transport/tmp PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/workspace/casepath-release-ae0-shard5/casepath-api:/workspace/casepath-release-ae0-shard5/casepath-api/tests /workspace/casepath-release-ae0-shard6/.runtime/casepath-dev-v2/venv/bin/python -m pytest -q casepath-api/tests/test_hosted_snapshot_transport_v1.py --junitxml=/workspace/knowledge-read-warm-20261016/transport/artifacts/metadata-green.xml > /workspace/knowledge-read-warm-20261016/transport/artifacts/metadata-green.log 2>&1; result=$?; cat /workspace/knowledge-read-warm-20261016/transport/artifacts/metadata-green.log; exit "$result"
```

Cleanup failing-first (exit 1, 1 expected failure, 5 deselected, 2.31 seconds):

```bash
HOME=/workspace/knowledge-read-warm-20261016/transport/home TMPDIR=/workspace/knowledge-read-warm-20261016/transport/tmp TEMP=/workspace/knowledge-read-warm-20261016/transport/tmp PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/workspace/casepath-release-ae0-shard5/casepath-api:/workspace/casepath-release-ae0-shard5/casepath-api/tests /workspace/casepath-release-ae0-shard6/.runtime/casepath-dev-v2/venv/bin/python -m pytest -q casepath-api/tests/test_public_hosted_read_only_v1.py -k cleanup_fails --junitxml=/workspace/knowledge-read-warm-20261016/transport/artifacts/cleanup-red.xml > /workspace/knowledge-read-warm-20261016/transport/artifacts/cleanup-red.log 2>&1; result=$?; cat /workspace/knowledge-read-warm-20261016/transport/artifacts/cleanup-red.log; exit "$result"
```

Combined followup regressions (exit 0, 51 passed, 18.07 seconds):

```bash
HOME=/workspace/knowledge-read-warm-20261016/transport/home TMPDIR=/workspace/knowledge-read-warm-20261016/transport/tmp TEMP=/workspace/knowledge-read-warm-20261016/transport/tmp PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/workspace/casepath-release-ae0-shard5/casepath-api:/workspace/casepath-release-ae0-shard5/casepath-api/tests /workspace/casepath-release-ae0-shard6/.runtime/casepath-dev-v2/venv/bin/python -m pytest -q casepath-api/tests/test_hosted_snapshot_transport_v1.py casepath-api/tests/test_public_hosted_read_only_v1.py --junitxml=/workspace/knowledge-read-warm-20261016/transport/artifacts/followup-green.xml > /workspace/knowledge-read-warm-20261016/transport/artifacts/followup-green.log 2>&1; result=$?; cat /workspace/knowledge-read-warm-20261016/transport/artifacts/followup-green.log; exit "$result"
```

Strengthened startup entry regression (exit 0, 1 passed, 5 deselected, 2.68 seconds):

```bash
HOME=/workspace/knowledge-read-warm-20261016/transport/home TMPDIR=/workspace/knowledge-read-warm-20261016/transport/tmp TEMP=/workspace/knowledge-read-warm-20261016/transport/tmp PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/workspace/casepath-release-ae0-shard5/casepath-api:/workspace/casepath-release-ae0-shard5/casepath-api/tests /workspace/casepath-release-ae0-shard6/.runtime/casepath-dev-v2/venv/bin/python -m pytest -q casepath-api/tests/test_public_hosted_read_only_v1.py -k startup_verifies --junitxml=/workspace/knowledge-read-warm-20261016/transport/artifacts/startup-entry.xml > /workspace/knowledge-read-warm-20261016/transport/artifacts/startup-entry.log 2>&1; result=$?; cat /workspace/knowledge-read-warm-20261016/transport/artifacts/startup-entry.log; exit "$result"
```

Metadata/cleanup commit source SHA-256:

```text
e38ce33e138f85a1d5abdab8ca8e03ce0a6f9d2fd800558d13be2f129764ce17  casepath-api/casepath_api/hosted_sql_v1.py
ef58f913f35002e00aad77350d1bd5258ecbe5d4f434f2a4a3ddd6fcff625e2d  casepath-api/casepath_api/hosted_app_v1.py
2f42771a0ce313b23bf26845aa60b3439daf741196984b1e67ba3cf994a2b610  casepath-api/tests/test_hosted_snapshot_transport_v1.py
710bc22ac117b58768de9a492351b1f6f58766eb3cb9e5895861295d7af519d4  casepath-api/tests/test_public_hosted_read_only_v1.py
```

## Concurrent shared-client regression

At the Mac integration owner's request, `7c2f36c027a266c87d6b3f1a54bd24931a7f1a64`
adds one test only. A custom MockTransport has per-request rotating baton
sessions and two barriers that require two real worker threads to overlap at
BEGIN and the later SELECT. Both connections populate independent prefetch
caches over the same shared HTTP client. One SELECT loses its response and
poisons/closes its connection with no retry or hidden rollback. The healthy
connection then reads its intact cache, commits and closes its own session.
Closing either connection leaves the HTTP client open; database close ends it.
The test avoids SQLite's thread constraints by constructing bounded synthetic
Hrana responses directly. No application/transport source changed in this commit.

Focused new test only (exit 0, 1 passed, 45 deselected, 0.08 seconds):

```bash
HOME=/workspace/knowledge-read-warm-20261016/transport/home TMPDIR=/workspace/knowledge-read-warm-20261016/transport/tmp TEMP=/workspace/knowledge-read-warm-20261016/transport/tmp PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/workspace/casepath-release-ae0-shard5/casepath-api:/workspace/casepath-release-ae0-shard5/casepath-api/tests /workspace/casepath-release-ae0-shard6/.runtime/casepath-dev-v2/venv/bin/python -m pytest -q casepath-api/tests/test_hosted_snapshot_transport_v1.py -k concurrent_shared_http --junitxml=/workspace/knowledge-read-warm-20261016/transport/artifacts/concurrent.xml > /workspace/knowledge-read-warm-20261016/transport/artifacts/concurrent.log 2>&1; result=$?; cat /workspace/knowledge-read-warm-20261016/transport/artifacts/concurrent.log; exit "$result"
```

Final source SHA-256:

```text
e38ce33e138f85a1d5abdab8ca8e03ce0a6f9d2fd800558d13be2f129764ce17  casepath-api/casepath_api/hosted_sql_v1.py
ef58f913f35002e00aad77350d1bd5258ecbe5d4f434f2a4a3ddd6fcff625e2d  casepath-api/casepath_api/hosted_app_v1.py
13fad77798af9ff38f06eb61b0b5d4b1f1f9c98a5cd2d91040aecf50a5d6747a  casepath-api/tests/test_hosted_snapshot_transport_v1.py
710bc22ac117b58768de9a492351b1f6f58766eb3cb9e5895861295d7af519d4  casepath-api/tests/test_public_hosted_read_only_v1.py
```
