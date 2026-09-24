# CasePath software

CasePath is released with the paper as agentic software for claims handlers.
This page describes it: what it is, how it operates, and how it relates to the method and the
benchmarks of the paper. The [repository README](../README.md) is the entry
point for the whole release.

![The workbench on a fictional claim: original notices beside the current process step and a human-review action.](../docs/images/workbench-review.png)

## What it is

A local, single-user workbench for deciding what evidence a claim needs now,
and why, before anything goes to the customer. It is a static browser interface
(this folder) over a FastAPI service ([`casepath-api/`](../casepath-api/)) that
stores every change to a claim as an event in a hash-chained SQLite journal. It
opens the 150 synthetic tenancy claims of Study B with their original messages
and attachments. The default mode makes no model calls and needs no API key.
Nothing is sent to a customer or settled.

## How it operates

1. **Intake.** Each claim arrives as it would in a claims inbox: the customer
   message, its channel and date, and any attachments. Source files are
   hash-checked before the service starts.
2. **Process.** The claim is placed in one of three process templates (defect,
   lease termination, rent increase), each with its steps, transitions and
   evidence requirements.
3. **Agent review.** Six roles run in a fixed order: facts, orchestration,
   source integrity, process, evidence, and audit and readiness. Only the
   process role may change claim state, and it does so through the journal.
   The released review is deterministic.
4. **Handling.** The handler reads the sources beside the current process
   step, the evidence to check and the next action; asks *Why this?* for any
   requirement; registers or corrects evidence; exports the claim status; and
   replays the journal read-only (`./bin/casepath replay <claim-id>`).

Views: the claim queue; the claim workbench with **Sources**, **Decision**,
**Evidence**, **All steps** and **Work log**; the read-only
[corpus browser](corpus.html) of all 150 intake packets; and the
[method page](method.html), which runs the paper's Study B controller on an
authored teaching example.

## How it relates to the paper

The paper measures the method, not this software. The three parts are kept
apart:

| Part | Role | Where |
|---|---|---|
| Study A condition interpreter and planner | The method as evaluated in Study A, installed in the service as a separate endpoint (`/api/paper-method`). Replaying the recorded condition decisions through it reproduces the documents, verdicts and next actions of all 72 cases and 36 paired changes. | [`casepath_api/`](../casepath-api/casepath_api/); [parity record](../research/casepath/branch-benchmark/parity/PRODUCT_METHOD_PARITY_V5.json) |
| Study B controller and evidence planner | The method as evaluated in Study B: full process scope, timing and route choice. Shown on the method page. | [`obligation_control/`](../casepath-api/casepath_api/obligation_control/) |
| Workbench and agent review | Product behaviour: source grounding, journaled state, correction and replay. It inherits none of the paper's measured results. | this folder, [`docs/AGENT_REVIEW.md`](../docs/AGENT_REVIEW.md) |

A live run of the Study A endpoint needs a model provider key and covers theft
claims only; the parity check replays recorded decisions offline.

## Run it

From the repository root:

```sh
./bin/casepath prepare     # once; installs pinned Python 3.13.9 dependencies with uv
./bin/casepath dev         # serves the workbench at the printed local address
./bin/casepath test        # full isolated test suite
```

Append `#claim=clm_f69b1747447bc221` to the printed address to open a recorded
example, then select **Start agent review**. [Setup](../docs/setup.md) covers
requirements, replay, export and reset;
[architecture and authority](../docs/architecture-authority.md) explains how
claim state is stored and changed.

## Status and limits

The workbench runs on macOS and Linux, on loopback for one user, without
authentication. It demonstrates handling mechanics, not legal
correctness or fitness for real claims. Historical release metadata names hosted services that run an older source
line; the local workbench is the verified one.
