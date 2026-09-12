# CasePath API

The FastAPI service supplies the standalone browser workspace, claim-loop
controller, source artifacts, deterministic orchestration, and compatibility
routes. Normal local use starts at the repository root:

```bash
./bin/casepath prepare
./bin/casepath dev
```

The launcher serves the API and frontend together at
`http://127.0.0.1:4173`, verifies the source capsule, selects deterministic
reference mode, and stores the durable journal under `.runtime`. See
[`docs/contracts-api.md`](../docs/contracts-api.md) for route and configuration
details.

Generated PDFs, messages, photographs, and page images live under ignored
`casepath-api/artifacts/`. They are reproduced from committed inputs and bound
by `artifact-manifest.json`; run `./bin/casepath prepare` rather than committing
the generated directory.

Direct `uvicorn` startup is intended only for targeted development. It omits
the launcher's complete manifest, capsule, same-origin, lock, and durable-state
checks. The supported package path needs no API key or provider call.
