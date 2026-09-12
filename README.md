# CasePath

CasePath is a local claims workbench for inspecting original sources, tracking
evidence, recording handling actions, and replaying the resulting journal. This
repository contains the complete standalone product, tests, release tools, and
**60 public synthetic development claims**. The default runtime is deterministic:
it reads no model API key and makes no provider call.

For a manual ChatGPT Pro implementation session, start with
[the Pro handoff](docs/PRO_HANDOFF.md). For local use, the path from a fresh
clone to a useful claim journey is:

```bash
git clone https://github.com/KumarNavish/casepath.git
cd casepath
./bin/casepath prepare
./bin/casepath dev
```

You need Git, `uv`, `lsof`, and either `lockf` on macOS or `flock` on Linux.
The first `prepare` installs pinned Python 3.13.9 dependencies and therefore
needs internet access. Later deterministic use requires no provider account,
credential, database server, or cloud service. See [local setup](docs/setup.md)
for platform details.

Open **http://127.0.0.1:4173/**. Search for a claim, open its original message
or attachment, assign an owner, start the assessment, inspect the missing
evidence, and export the current status. Stop the server with Ctrl-C. The
journal and registered artifacts remain under `.runtime/casepath-data-v1`.

## Useful commands

```bash
./bin/casepath prepare
./bin/casepath dev
./bin/casepath test
./bin/casepath seed --corpus synthetic-dev-60
./bin/casepath replay <claim-id>
./bin/casepath adapter-check examples/local_source_adapter.py
```

`prepare` verifies the committed source manifest before generating ignored
artifacts or runtime state. It rejects an edited or incomplete source tree.
After authoring changes, follow the exact [source sealing
procedure](CONTRIBUTING.md#seal-authored-changes) before another launch.

## What the package establishes

The local workspace supports claim search, original-source inspection,
assignment, assessment start, evidence actions, status export, and journal
replay. Source bytes, observations, proposals, accepted actions, and read-only
projections remain separate. A model proposal never establishes a decision.

The 60 bundled cases are public synthetic development inputs. The 90 reserved
inputs from the former 150-case research collection are excluded and are not
recoverable from this repository. The development set is not an untouched
evaluation holdout. Deterministic tests establish product mechanics; they do
not establish legal correctness, model quality, operational readiness, or
fitness for real claims.

Paid native-source review has not been verified for this standalone package.
The Render services named in historical release records run an older,
separately sourced release. This repository has no deployment handoff and the
local package should not be judged against those hosted services.

## Documentation

- [Documentation index](docs/README.md)
- [Local setup and first claim](docs/setup.md)
- [Manual Pro implementation handoff](docs/PRO_HANDOFF.md)
- [Architecture and authority](docs/architecture-authority.md)
- [API and configuration](docs/contracts-api.md)
- [Troubleshooting and recovery](docs/troubleshooting.md)
- [Contributing and source sealing](CONTRIBUTING.md)
- [Migration provenance](docs/migration-provenance.md)
- [Validation record](docs/HANDOFF_VALIDATION.md)

The existing [LICENSE](LICENSE) is preserved from the source repository. See
[third-party notices](THIRD_PARTY_NOTICES.md) for bundled data and dependency
licensing.
