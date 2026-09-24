# Local setup and first claim

## Prerequisites

CasePath supports macOS and POSIX Linux. Install:

- Git;
- `uv`;
- `lsof`;
- `lockf` on macOS or `flock` on Linux.

The launcher installs pinned CPython 3.13.9 and dependencies. Node.js is needed
only for JavaScript browser QA. Native Windows has not been validated; use a
compatible Linux environment.

## Clone and prepare

```bash
git clone https://github.com/KumarNavish/casepath.git
cd casepath
./bin/casepath prepare
```

The first command may use the network to install the pinned environment.
`prepare` then verifies the sealed source roster before it generates ignored
documents and static output. It does not seed or open the durable product
journal.

If `prepare` reports source drift in an untouched clone, stop and compare the
checkout with `origin/main`; do not regenerate a manifest merely to silence an
unexpected difference.

## Start the local product

Confirm that no other process owns port 4173, then run:

```bash
./bin/casepath dev
```

Open http://127.0.0.1:4173/. Keep the command running and use Ctrl-C to stop it.
The launcher serves the frontend and API from one loopback origin, unsets model
and tracing credentials, and forces deterministic reference mode.

## Walk through a claim

1. In **Claims**, select **Walk through this claim**, or open
   `http://127.0.0.1:4173/#claim=clm_f69b1747447bc221`. The list groups claims
   by who CasePath is waiting for. **Filter** opens the extra queue controls.
2. Select **Review claim**. Watch findings appear in **What I noticed** and
   follow a highlighted line to the customer message or PDF in **Sources**.
   **Stop** cancels a running review.
3. Read **Where it stands**: done, now, next, then **+8 later**. The conditions
   and their source quotes sit below the steps. **Why** shows the reason for the
   next step.
4. Read **Questions** and **What to request**. The two notices have different
   end dates; the receipt dates remain open. Documents are grouped under
   **Now**, **Later**, and **Not needed**.
5. Focus family-home service, select **what if**, and set it false. Read the changed
   path and request, then **Exit** to return to the saved claim.
6. Select **Draft request**. Edit the letter in place, then use **Save edits**,
   **Copy**, or **Export**. The draft is labelled **Draft, not sent**.
7. Stop the server and replay the selected claim:

```bash
./bin/casepath replay <claim-id>
```

The replay is read-only. Restart `./bin/casepath dev` and confirm that the
findings, path, and draft still appear. **About** contains the Reviewer mode
switch for provenance labels; **Technical details** holds the recorded checks.

Screen references: [Claims list](images/workbench-queue.png),
[reviewed claim at 1440 px](images/workbench-review.png), and
[reviewed claim at 390 px](images/workbench-mobile.png).

## Local state

Runtime files are ignored by Git:

| Path | Purpose |
| --- | --- |
| `.runtime/casepath-dev-v2` | pinned environment, source capsules, boot receipts, and temporary files |
| `.runtime/casepath-data-v1/casepath.db` | durable hash-chained SQLite journal |
| `.runtime/casepath-data-v1/agent-work-v1.sqlite3` | persisted six-role review work and events |
| `.runtime/casepath-data-v1/artifact-registry` | locally registered source artifacts |
| `casepath-api/artifacts` | generated source artifacts |
| `casepath-public` | generated same-origin static build |

Use a fresh clone for destructive or disposable experiments. Do not delete an
existing `.runtime/casepath-data-v1` to fix a launch error; preserve it and use
[troubleshooting](troubleshooting.md).

## Next steps

- Run `./bin/casepath adapter-check examples/local_source_adapter.py` to verify
  the provider-neutral source registration boundary.
- Read [Agent review workflow](AGENT_REVIEW.md) for the six-role and external-Facts boundaries.
- Read [API and configuration](contracts-api.md) before calling mutations.
- Read [Contributing](../CONTRIBUTING.md) before changing source.
