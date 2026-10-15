Bounded operation transport implementation is pushed on `codex/operation-stream-transport-20261015`.

- Base: `d0d0fa7f9041f7405f1d8393bacd47d4332ee79b`.
- Commit: `4c5bce3ea912aa025eb42c7b75bad059e631b123` (`perf: batch and gzip bounded operation streams`).
- Actual host: `656813ef2295`; checkout `/workspace/casepath-stream-transport-20261015`.
- Exactly four changed files: `casepath-api/casepath_api/autonomous_api_v1.py`, `casepath-api/tests/test_autonomous_operations_v1.py`, `casepath/tools/sites_worker.mjs`, `casepath-qa/sites-proxy.test.cjs`.
- Exact patch: `transport.patch`; working tree was clean after commit/push.

The API selects identity or gzip using all Accept-Encoding field lines, explicit qvalues/identity preferences and exclusions, wildcard fallback, and conservative invalid/duplicate weights. A request excluding both supported encodings receives406 before worker admission. The first binding is immediately yielded and gzip sync-flushed; subsequent available frames are batched up to64KiB or10ms of drain work. A larger frame is yielded alone. There is no accumulation sleep. A single pending lookahead retains its byte/count charge, preserving the8-frame/2MiB waiting budget. Existing2MiB frame bound, total engine bounds, deadline checks, worker ownership, and cleanup remain in force. Disconnect cancellation is set before any gzip footer yield.

The Sites change forwards Accept-Encoding only on the operation route, retaining the existing14s timeout and cancellation. It keeps the native Fetch response body unread and Content-Encoding intact. This follows Cloudflare's documented compressed-origin pass-through contract; it does not infer Node Fetch decompression behavior or set encodeBody manually. Official source receipts and8 independent lifecycle checks are owned by the reviewer under `../review/`. The Node tests prove header and raw mocked-body pass-through, not execution inside the deployed Cloudflare runtime.

Final validation uses the exact committed source bytes. `final-start-source-sha256.txt` and `final-end-source-sha256.txt` are identical; the full command/environment setup is retained in `final_checks.sh`.

```text
/workspace/casepath-release-ae0-inventory/.runtime/casepath-dev-v2/venv/bin/python -m pytest -q -p no:cacheprovider --junitxml=/workspace/cp-stream-transport-evidence-20261015/writer/python-affected-final.junit.xml casepath-api/tests/test_autonomous_operations_v1.py -k operation_transport
42 passed,18 deselected,5 third-party Swig deprecation warnings; exit0;20.60s

/opt/codex/runtimes/codex-primary-runtime/dependencies/node/bin/node --test casepath-qa/sites-proxy.test.cjs
12 passed,0 failed/cancelled/skipped/todo; exit0
```

The final42 API tests include negotiation, repeated field lines, live+recorded exact decoded NDJSON equality and output/trace/operation-chain hashes, both encodings, immediate incremental binding, bounded batches, byte backpressure, aggregate lookahead budgeting, per-frame rejection, cancellation, deadline and error framing. Live/recorded tests use the existing deterministic migrated synthetic fixture and forbid writer constructors/append/publish; recorded reads also forbid recomputation/input capture. They are fixture evidence, not production-head or hosted network validation. No native API compression ratio/ASGI-count measurement was emitted by this run; no production performance claim is made.

Earlier wider verification ran:

```text
/workspace/casepath-release-ae0-inventory/.runtime/casepath-dev-v2/venv/bin/python -m pytest -q -p no:cacheprovider casepath-api/tests/test_autonomous_operations_v1.py casepath-api/tests/test_operation_trace_storage_v1.py
67 passed,5 third-party Swig deprecation warnings; exit0;96.67s
```

That run preceded the final lookahead charge/counter fix and its two new regressions, so `python-focused-green-1.log` is explicitly an earlier-stage full-module pass. Only affected transport/Sites checks were repeated after the final change. `python-controlled-green-1.log` records an earlier36-test controlled pass; `node-green-1.log` records an earlier12-test proxy pass.

Negative attempts are preserved and classified:

- `python-red.log`: first authoring attempt,32 failures/2 setup errors/18 deselected,exit1. Controlled harness omitted a service.store attribute and real fixtures lacked ignored generated PDF assets. This is setup/harness evidence, not valid proof of product regressions. The harness was corrected and only ignored static API artifacts were generated from this checkout using `generate_artifacts.py` and `replace_photographic_evidence.py .`; both exit0 (`artifacts-setup.log`, `photos-setup.log`). No foreign journal or production-head fixture was copied.
- `python-original-red.log`: corrected regression replay against immutable original API source,36 expected failures/4 passed/18 deselected,exit1,24.33s. `replay_original_transport.py` compiles `autonomous_api_v1.before.py` into the module in memory without editing the checkout. Its API SHA256 matches `baseline-source-sha256.txt`. Failures prove missing compression, Vary/negotiation and batching on the original transport. The selected tests precede the final two lookahead cases.
- `node-red.log`:10 passed/2 expected new negotiation failures,exit1,against original Worker.
- `python-lookahead-red.log`:2 expected failures/58 deselected,exit1,against saved pre-accounting-fix implementation. `replay_lookahead_regression.py` loads `api-before-lookahead-fix.py` in memory; `before-lookahead-fix-sha256.txt` identifies that implementation. Both encodings let four excess400k frames refill while a1.5MiB lookahead remained unsent; final tests pass after retaining its charge.
- Push succeeded (`push.log`). The remote also emitted its existing default-branch dependency advisory banner; no dependency changes belong to this task.

All test subprocesses used TMPDIR/TMP/TEMP=`/workspace/cp-stream-transport-evidence-20261015/tmp`, HOME=`/workspace/cp-stream-transport-evidence-20261015/home`, PYTHONDONTWRITEBYTECODE=1 and PYTHONPATH pointing at this checkout's API. Managed proxy/CA/auth bindings were inherited, not overwritten or printed. `inherited-binding-names-only.txt` contains names/presence only. The first read-only inspection commands preceded task TMP exports; every test and generated-asset command used the required environment. No install, dependency change, provider/model call, product public-network request, seal/fullgate, deploy, head cache, engine/trace/data/frontend semantic edit, or unrelated cleanup was performed. Git source publication was explicitly authorized. Mac owns final sealing/integration.

The existing cooperative10s runtime deadline is preserved. This patch does not add an absolute ASGI-send/download watchdog; bytes already handed to a slow downstream connection remain subject to the existing serving stack. The reviewer independently tested first-binding iterator close and disconnect cancellation for both encodings. No hosted/Cloudflare production execution is claimed.
