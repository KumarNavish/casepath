# Test suite — 975 pass, 7 fail, and the 7 are not this work

Full run after the interpreter and induction changes: **975 passed, 7 failed, 10 skipped** in 14m29s.

## The 7 failures

All in `tests/test_cli_v1.py`, all variants of the same cause. Example:

```
test_adapter_check_rejects_local_implementation_source_drift
  expected: 'drifted during conformance'
  actual:   'source manifest file identity differs from disk'
```

The adapter refuses to run before reaching the behaviour under test, because `casepath/source-manifest.json`
records a SHA-256 per file and ten files on disk no longer match it:

`.gitignore`, `agent_work/runtime.py`, `arena_v1/{generator,product_corpus_study,run_turn,runner,write_episodes}.py`,
`evidential_channel_v1.py`, `native_inference_v1.py`, `native_live_workspace_v1.py`.

## Why they are not caused by this work

Two independent checks.

**None of the drifted files is one this work touched.** Every one of the ten was last modified on 2026-09-15, in
the previous session — the `_write_exact` concurrency fix, the agent-work requirement-scope fix, the empty-completion
fix in `run_turn`, the provider-pin flag in `product_corpus_study`, and the release packaging change to
`.gitignore`. The manifest was not regenerated after those commits.

**None of this work's modules is in the manifest at all.** `case_interpreter_v1.py`, `process_induction_v1.py`,
`obligation_compiler_v1.py`, `authority_corpus_v1.py`, `process_experiment_v1.py`, `contract_scoring_v1.py` and
`casepath_process_service_v1.py` are absent from its 1348 entries, so editing or adding them cannot move a hash it
records.

The failures therefore pre-date today and would appear on a checkout of the state this session inherited.

## Not fixed here, deliberately

The fix is to regenerate `casepath/source-manifest.json`. That file is owned by the product work and is on the
explicit do-not-touch list for this session, so it is left alone and reported instead. Regenerating it is a
one-line operation for whoever owns the release, and the 7 tests should pass immediately afterwards.

## What does pass

The 975 include every test covering the modules this work changed, and the artifact check
(`research/casepath/verify_artifacts.py`) passes independently: 130 authority passages with 0 hash mismatches,
every reference-contract quote still verbatim against the passage it is attributed to, and 0 cases leaked between
the development and confirmatory splits.
