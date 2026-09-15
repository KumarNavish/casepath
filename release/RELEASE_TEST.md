# Release test

```bash
release/release_test.sh
```

prints `PASS` and exits 0, or `FAILED` and exits 1. It runs the method, harness and product tests, then
reproduces every number the paper cites from the committed raw records without calling a model.

## What it excludes, and why

`tests/test_cli_v1.py` contains seven failures that **predate this work and are unrelated to it**. They were
failing at the untouched baseline commit `fac1f4c`, before any research change, and they touch no file this
work modifies:

```
test_audited_local_adapter_completes_exact_once_lifecycle
test_adapter_check_rejects_local_implementation_source_drift
test_adapter_check_rejects_transitive_source_drift
test_seed_rejects_source_drift_after_service_construction
test_seed_withholds_receipt_when_source_drifts_during_mutation
test_adapter_static_byte_cap_has_exact_boundary
test_launcher_safe_path_blocks_caller_package_shadow
```

All seven concern the CLI's adapter source-drift detection and a static byte cap. To see that they are
pre-existing rather than introduced:

```bash
git stash && git checkout fac1f4c -- casepath-api && \
  (cd casepath-api && python -m pytest tests/test_cli_v1.py -q) ; git checkout HEAD -- casepath-api && git stash pop
```

The whole suite is `pytest tests/ -q` and reports `7 failed, N passed`. That number is stated in the paper
rather than hidden, and the release target above is the unambiguous one.
