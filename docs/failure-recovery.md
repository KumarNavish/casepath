# Failure and recovery

For symptom-based diagnosis, start with [troubleshooting](troubleshooting.md).

`./bin/casepath dev` owns one kernel-backed launch lock, one pinned Python
runtime, one same-origin listener, and one SQLite journal. It validates the
source manifest and built static inventory before and after child startup.

On restart, the service replays hash-chained events and repairs derived
checkpoints and indexes. A corrupt journal is terminal; derived cache corruption
may be discarded and rebuilt only from validated events. Idempotency prevents a
lost response from duplicating an accepted command. Unknown external effects
remain explicit until their persisted adapter state is reconciled.

Useful diagnostics:

```bash
./bin/casepath replay <claim-id>
./bin/casepath seed --corpus synthetic-dev-60
./bin/casepath test
```

Replay opens the database read-only and performs no repair. If port 4173 is
already owned, the launcher fails before advertising a URL. `Ctrl-C` terminates
only the owned server and retains local journal state.
