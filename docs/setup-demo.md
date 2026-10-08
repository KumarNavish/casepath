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

Also acquire the model's endpoint roster from OpenRouter's
`/api/v1/models/{author}/{slug}/endpoints` route. Save a local packet with `at`
(the UTC retrieval time), `status` (200), and `response` (the complete JSON
response). It must be no more than 24 hours old. The launcher checks the exact
model, required tool-call support, the actual request parameters, and the
catalogue price ceiling before reading the credential. A catalogue entry saying
“tools” alone does not establish endpoint compatibility. The launcher does not
fetch this file or change account routing preferences.

Store the authorized credential in macOS Keychain under service
`CasePath OpenRouter demo`, with the account equal to the current macOS login
name. Use Keychain Access or a trusted credential setup flow. Do not put the
credential in a shell argument, source file, catalogue, receipt or command log.
The launcher reads it privately after local verification and passes it only to
the serving child. It ignores an inherited `OPENROUTER_API_KEY`.

Start the demo from the repository root with the selected catalogue-bound model:

```sh
.runtime/casepath-dev-v2/venv/bin/python -I -B -P casepath/tools/run_agent_demo.py \
  --model 'openai/gpt-4.1-nano' \
  --catalogue .runtime/casepath-openrouter-demo/catalogue-nano.json \
  --endpoints .runtime/casepath-openrouter-demo/endpoints-nano.json
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

CasePath's source reader first opens the original packet through the same
checked, recorded tools. The model receives those source texts and selects exact
passages. Every selection is checked; rejected selections stay in the record.
The host copies accepted quotations into reported assertions and finishes through
the existing checked tools, with no further model request for those mechanical
steps. Source reads, publication and completion are labelled as kernel work and
count toward the shared tool budget. Failed preparation or an oversized request
stops before inference. Completion records bounded checked statements and source
coverage; it does not establish that every possible fact was extracted. The
model cannot convert a quoted statement into a confirmed claim fact.

The review opens while current work is observed and stays in place through its
completion. Closing it or making a fresh visit lets completed history sit below
the next handler decision. Stage selectors name Sources, Findings, Process and
Documents; the selected stage shows its count and status, with Review recorded
for a completed stage. These summaries describe saved work and citations, not
private model reasoning. On screens at or below 540 px, the claim panel owns a
single vertical scroll region.

## Receipts and shutdown

### One explicitly approved extra review

The original three-run policy is immutable. If all three runs have been used,
an operator may prepare a separate one-run amendment for explicit human
approval. Do not run the following operation until that approval is given.
It enables exactly one fourth review while preserving the 18-request limit,
USD 0.02 per-review limit, USD 0.10 aggregate limit, all earlier usage and every
unknown-cost reservation. No fifth review or second distinct amendment is
available.

Read the complete current `external_budget` from the local capabilities
projection and retain its canonical SHA-256 before asking for approval. Stop
the owned server. The operation requires the same clean commit, normal-boot
verification and runtime/data leases as serving, then writes only the sealed
allowance receipt in the existing work store:

```sh
.runtime/casepath-dev-v2/venv/bin/python -I -B -P casepath/tools/run_agent_demo.py \
  --grant-one-extra-run \
  --expected-budget-sha256 '<approved prior budget SHA-256>' \
  --actor '<approving operator>' \
  --reason '<recorded approval reason>' \
  --idempotency-key '<unique approval key>'
```

It reads no credential, starts no server and makes no provider request. A stale
budget, active work, pending provider outcome or altered receipt prevents the
grant. Exact retries recover the same receipt; they do not add another run.
If the command's outcome is unknown, inspect the saved receipt before retrying.
After a confirmed grant, launch the ordinary demo command and start the review
through its existing native control. The launch receipts retain the effective
run cap and grant hash separately from the base policy.

### Launch records

Each launch writes a new private directory under
`.runtime/casepath-openrouter-demo/`, containing the pinned public catalogue,
endpoint snapshot and
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

At **8 October 2026, 16:08 UTC**, commit `382dd6c` passed 1,845 backend/static
tests (ten skipped) and the normal frontend/API identity check. Two explicit
provider attempts remain recorded: Haiku's endpoints rejected the required
tool-call mode with HTTP 404; nano reached six requests before completing its
source reads. The latter reported USD 0.000721. The first attempt's USD 0.0028
reservation remains because no usage was reported. Neither run completed or
changed the claim. The endpoint guard and bounded source preparation are the
subsequent correction; their final runtime acceptance is recorded separately.

At **8 October 2026, 17:10 UTC**, commit `c399bfc` passed 1,868 backend/static
tests (ten skipped), prepared and booted with matching frontend/API identity.
The third explicit live attempt accepted one exact 220-character passage and
rejected another selection, then stopped before its second provider request
because the conversation exceeded 24 KB. It reported USD 0.000742; the claim
remained at revision 167. The aggregate reported cost is USD 0.001463, with the
earlier USD 0.0028 unknown-cost reservation retained. The base three-run
allowance is exhausted. The subsequent host publication path and optional
explicit amendment are implemented for verification; no amendment or successful
new live run is claimed by this checkpoint.
