# Contributing to CasePath

Start with [local setup](docs/setup.md) and read
[architecture and authority](docs/architecture-authority.md) before changing
state, evidence, or API behavior.

Keep these invariants intact:

1. Use `/api/claim-loops/v1` as the mutation control plane.
2. Keep source bytes, observations, interpretations, proposals, and accepted
   journal events separate.
3. Never infer readiness from UI state, corpus labels, caller-authored artifact
   identifiers, or model output.
4. Preserve exact idempotency, expected-revision checks, restart, and replay
   behavior.
5. Add a failing invariant test before changing safety-sensitive code.
6. Use public synthetic fixtures and deterministic local mode for routine work.
7. Verify the changed behavior in an isolated local instance.

Do not add credentials, real claims, private records, the 90 reserved research
inputs, benchmark targets, provider calls, or external effects to fixtures.
Older QA programs that name 150 claims preserve historical contracts; they are
not the fresh-clone acceptance path for the 60-case public package.

## Development loop

Prepare an unchanged clone once:

```bash
./bin/casepath prepare
```

Make a focused change, run the smallest meaningful regression, and inspect the
affected workflow. The complete deterministic suite is:

```bash
./bin/casepath test
```

The complete suite is intentionally broad and can take about 13 minutes on the
validated macOS host. Run it when the change crosses subsystem boundaries or
before a release candidate; do not use historical paid or hosted QA scripts as
routine validation.

## Seal authored changes

The source manifest is content-only and covers the application, API, QA, docs,
examples, launcher, root documentation, `AGENTS.md`, `.gitattributes`, and the
other explicit release files. Generate it only after every authored edit is
complete.

If a script or stylesheet referenced by `casepath/index.html` changes, first
update that asset's existing `sha256` query value to the value printed by:

```bash
shasum -a 256 <asset-path>
```

Then stop any development server owned by this checkout and run these commands
from the repository root exactly:

```bash
set -e
export SOURCE_DATE_EPOCH=1786406400
export CASEPATH_SOURCE_COMMIT="$(git rev-parse HEAD)"
export PYTHONDONTWRITEBYTECODE=1
.runtime/casepath-dev-v2/venv/bin/python casepath-api/generate_artifacts.py
.runtime/casepath-dev-v2/venv/bin/python casepath-api/replace_photographic_evidence.py .
.runtime/casepath-dev-v2/venv/bin/python casepath/tools/build_static_site.py --require-known-commit
.runtime/casepath-dev-v2/venv/bin/python casepath/tools/casepath_release.py generate
./bin/casepath test
```

Review and commit the authored source plus `casepath/source-manifest.json`.
Generated API artifacts, `casepath-public/`, environments, and runtime state are
ignored. The manifest deliberately omits its containing Git commit; runtime
receipts bind the actual checkout commit.

After committing, run:

```bash
./bin/casepath prepare
```

This verifies the sealed source before regenerating ignored artifacts and
records the new Git identity in runtime receipts. See
[troubleshooting](docs/troubleshooting.md) if source verification fails.
