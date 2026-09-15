# CasePath

CasePath is a local claims workbench for inspecting original sources, tracking
evidence, recording handling actions, and replaying the resulting journal. This
repository contains the complete standalone product, tests, release tools, and
**all 150 original synthetic intake claims**. The default runtime is deterministic:
it reads no model API key and makes no provider call. The current workbench also
includes a persisted six-role **Agent review** chain with inspectable source reads,
handoffs, gates, process/evidence mappings, and readiness checks. An external model
may replace Facts only through an explicit, bounded developer path; it is never an
automatic fallback.

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

Open **http://127.0.0.1:4173/**. Search for a claim, inspect its original packet,
start the assessment, and open **Agent review** to see the six specialists and their
recorded handoffs. Evidence, process, correction, and next-action surfaces remain
connected to the same authoritative claim journal. Stop the server with Ctrl-C.
The journal, agent-work store, and registered artifacts remain under
`.runtime/casepath-data-v1`.

## Useful commands

```bash
./bin/casepath prepare
./bin/casepath dev
./bin/casepath test
./bin/casepath seed --corpus synthetic-150
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

The operational workspace includes every original intake packet in `synthetic-150`:
150 customer communications and their 57 attached documents (47 PDFs and 10 JPEGs).
The original source bytes and claim identifiers are preserved. No sealed answers,
expected outputs, evaluator gold, or selected process paths are included. The prior
`synthetic-dev-60` package remains immutable for regression tests; it is not the
main workspace. These inputs have now been inspected during product development
and must not be described as untouched evaluation inputs.

The packet viewer renders PDF pages and images from the original bytes, supports
bounded Word text and saved spreadsheet-cell previews, and never turns a preview
into accepted evidence. The original 150 inputs contain no Word or spreadsheet
attachments; those formats are verified with separate synthetic unit fixtures.

Deterministic tests establish product mechanics, not legal correctness, model
quality, production readiness, or fitness for real claims. See
[the intake-packet release](docs/INTAKE_PACKET_150.md) for provenance and scope.

A real external Facts-worker acceptance has now been verified against the actual
installed application. The accepted run used OpenRouter with
`cohere/north-mini-code:free`, produced 6 genuine provider responses, completed
through the same grounded tools and deterministic gates, and survived a later
credential-free restart without another model call. This proves one bounded
external-worker substitution, not general model quality or legal correctness. See
[Agent review workflow](docs/AGENT_REVIEW.md).

The Render services named in historical release records run an older, separately
sourced release. This repository has no deployment handoff and the local package
should not be judged against those hosted services.

## Documentation

- [Documentation index](docs/README.md)
- [Local setup and first claim](docs/setup.md)
- [Manual Pro implementation handoff](docs/PRO_HANDOFF.md)
- [Architecture and authority](docs/architecture-authority.md)
- [Agent review workflow and acceptance](docs/AGENT_REVIEW.md)
- [API and configuration](docs/contracts-api.md)
- [Troubleshooting and recovery](docs/troubleshooting.md)
- [Contributing and source sealing](CONTRIBUTING.md)
- [Migration provenance](docs/migration-provenance.md)
- [Validation record](docs/HANDOFF_VALIDATION.md)

The existing [LICENSE](LICENSE) is preserved from the source repository. See
[third-party notices](THIRD_PARTY_NOTICES.md) for bundled data and dependency
licensing.
