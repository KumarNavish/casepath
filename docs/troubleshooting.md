# Troubleshooting

CasePath fails closed when source, runtime, journal, or listener identity is
uncertain. Preserve the reported error and diagnose the corresponding boundary.

## `uv` or Python setup fails

Confirm that `uv` is executable, or set `CASEPATH_UV` to its absolute path.
The first preparation needs network access for pinned CPython 3.13.9 and locked
dependencies. Later deterministic launches do not need provider access.

If a sibling checkout already has the exact environment, do not copy mutable
environment files into this repository. Let this checkout create and verify its
own `.runtime/casepath-dev-v2`.

## Source manifest verification fails

`prepare` verifies `casepath/source-manifest.json` before generating runtime
artifacts. In an untouched clone, inspect `git status` and compare with
`origin/main`. A missing file, changed byte, executable-bit change, unsealed doc,
or extra nonignored file inside a manifest root is a real mismatch.

For intentional source edits, complete all changes and follow
[the sealing commands](../CONTRIBUTING.md#seal-authored-changes). Do not hand-edit
manifest hashes or run generation repeatedly around unfinished edits.

## Port 4173 is occupied

The launcher refuses to seed, launch, or take over a foreign listener. Keep the
existing server and its state intact. Stop it only if you own it, or use a fresh
checkout after the existing task finishes. The public launcher does not expose
a configurable product port.

## A lock is busy

Another CasePath command may own the environment, data, or launch lease. Wait
for that command or stop it through its controlling terminal. Do not remove lock
files while a process may be alive; the launcher validates kernel ownership,
not only the file name.

## The journal does not start

The journal is lifecycle authority. A corrupt hash chain is terminal and must
not be repaired from UI state, cache, or a checkpoint. Keep
`.runtime/casepath-data-v1` unchanged, capture the error, and run read-only
replay for a known claim if the launcher permits it:

```bash
./bin/casepath replay <claim-id>
```

Derived indexes and checkpoints may be reconstructed only from validated
events. For disposable testing, reproduce in a fresh clone instead of deleting
the affected journal.

## A command was retried after an uncertain response

Reuse the exact idempotency key and request body. An exact retry returns the
accepted result; a different command under the same key fails. If an external
adapter effect is unknown, keep it unknown and use the supported reconciliation
path after checking the adapter's persisted status.

## Browser content looks stale

Stop the server, seal any intentional source edits, run `./bin/casepath prepare`,
and restart. The runtime serves a verified immutable source capsule and will not
silently load an edited asset. Check the browser at the exact loopback URL and
hard-refresh only after the new server reports ready.

For the underlying recovery model, see [failure and recovery](failure-recovery.md).
