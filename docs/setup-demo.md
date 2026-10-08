# Local demo with a bounded live facts role

The normal `./bin/casepath dev` remains deterministic and removes provider
credentials. The separate demo launcher enables an explicitly selected OpenRouter
facts role. A handler must start each live review. Startup, desk arrival and
ordinary claim refresh do not start provider work. The other review roles and
claim authority keep their existing local execution and approval boundaries.

This profile requires explicit authorization for the external processing and
costs. The current allowance is three manual runs, at most 18 provider requests,
USD 0.02 per run and USD 0.10 in aggregate. The work database retains the budget
across restarts; relaunching does not refill it. Unknown outcomes retain their
reservation and do not trigger an automatic inference retry. No draft is sent.

## Prepare the exact source

Finish the normal source sealing, full tests and local commit described in
[CONTRIBUTING.md](../CONTRIBUTING.md). Then run `./bin/casepath prepare` and
successfully start `./bin/casepath dev` for that exact commit. Wait for its ready
message, then stop it with Ctrl-C. Keep the runtime data and boot receipts.

The demo consumes the immutable capsule recorded by that normal boot. It rejects
dirty source, a different commit, source or interpreter drift, failed historical
validation, occupied port 4173, and a conflicting runtime lease. It verifies the
existing journal and boot history in read-only mode. It makes no normal boot
receipt and does not rewrite the normal zero-credential attestations.

## Configure the local inputs

Use an explicitly acquired OpenRouter model catalogue snapshot, no more than
24 hours old, at `.runtime/casepath-openrouter-demo/catalogue.json`. The directory
must be private to the current account (mode 0700). The packet contains
`fetched_at`, `catalogue`, and the SHA-256 of the canonical `catalogue` object
under `catalogue_sha256`. Choose an exact concrete tool-capable model ID from
that snapshot. The launcher does not fetch or refresh the catalogue.

Store the authorized credential in macOS Keychain under service
`CasePath OpenRouter demo`, with the account equal to the current macOS login
name. Use Keychain Access or a trusted credential setup flow. Do not put the
credential in a shell argument, source file, catalogue, receipt or command log.
The launcher reads it privately after local verification and passes it only to
the serving child. It ignores an inherited `OPENROUTER_API_KEY`.

Start the demo from the repository root with the selected catalogue-bound model:

```sh
.runtime/casepath-dev-v2/venv/bin/python -I -B -P casepath/tools/run_agent_demo.py \
  --model 'anthropic/claude-haiku-5.5' \
  --catalogue .runtime/casepath-openrouter-demo/catalogue.json
```

Open `http://127.0.0.1:4173/` after the demo ready message. The frontend and API
must report the same committed source. The capabilities projection must show
the chosen model and persisted demo allowance. Start live facts work through
the claim's **Controls** disclosure. Inspect **Review details** for the selected
model and synthetic-source scope, confirm the displayed per-review ceiling,
then choose **Review sources live**. The claim needs an accountable handler,
current context, an unpaused delegate and no unresolved work. The optional
rerun stays within the same disclosure. Running the launcher alone makes no provider call.
The legacy `/readyz` model budget describes the deterministic main pipeline;
the live facts allowance is the separate agent-work capabilities budget.

The review opens while current work is observed and stays in place through its
completion. Closing it or making a fresh visit lets completed history sit below
the next handler decision. Stage selectors name Sources, Findings, Process and
Documents; the selected stage shows its count and status, with Review recorded
for a completed stage. These summaries describe saved work and citations, not
private model reasoning. On screens at or below 540 px, the claim panel owns a
single vertical scroll region.

## Receipts and shutdown

Each launch writes a new private directory under
`.runtime/casepath-openrouter-demo/`, containing the pinned public catalogue and
separate `ready.json` and `stopped.json` profile receipts. They record source,
capsule, normal-boot identity, selected model, policy and observed usage. They
never contain the credential or raw environment. A missing shutdown observation
is recorded as unknown, not zero spend. Work journals remain the authority for
provider attempts, results, reservations and learned proposals.

The launcher holds the same environment and data leases as the normal product,
and passes them to its child. It binds localhost port 4173 before credential
access and passes that socket to the serving process. Ctrl-C stops the child and
preserves all history. If shutdown interrupts a provider request, inspect the
saved outcome before starting another run. The launcher never clears a pending
call, resets a budget, resends a request, or terminates another server.

The recorded runtime closure covers the immutable application capsule, pinned
interpreter and complete environment site-packages under the existing normal
boot checks. It does not claim a whole-host attestation. No new dependency or
frontend build step is required.

## Acceptance checkpoint

At **8 October 2026, 11:38 UTC**, live integration and its mocked-provider
invariants are implemented, but paid inference remains zero. The full V4 suite
recorded 1,830 passes, ten skips and one static-packaging failure. The omitted
work-motion module has been added to both asset inventories; eleven focused
build tests and 244 integrated frontend tests pass. A saved 390×844 check covers
the unsealed reference UI only. It does not verify the configured live-control
viewport or an actual provider journey.

The full suite for the changed source, final seal, commit and normal boot must
precede this launcher. The planned external evidence receipts
`v4-live-provider-acceptance.json` and `v4-final-release-receipt.json` will record
later provider and release outcomes; their existence or success is not claimed
at this checkpoint. See the [acceptance record](product/AGENT_NATIVE_ACCEPTANCE.md)
for retained failures and the remaining gates.
