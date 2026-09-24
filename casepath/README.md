# CasePath software

This directory contains the static CasePath workspace. Its queue names one fact
noticed on each claim. A claim opens with sources at left, the path in the
centre, and needs with the next step at right. Review lines, handler notes,
drafts, and memories are journaled separately from the original packet.

Run the product from the repository root with `./bin/casepath dev`. The local
launcher builds the curated static site and serves it with the API from
`http://127.0.0.1:4173`; no frontend package install is required.

The first-run card opens a five-step walk through the family-home claim.
Reviewer mode labels the provenance of displayed objects. [About
CasePath](method.html) links to the live What if control, data, and research.

Historical release metadata names hosted services, but those services run an
older source line. See
[`docs/architecture-authority.md`](../docs/architecture-authority.md) before
changing source, state, or evidence behavior.

## How it relates to the paper

The paper measures the method, not this software. The three parts are kept
apart:

| Part | Role | Where |
|---|---|---|
| Study A condition interpreter and planner | The method as evaluated in Study A, installed in the service as a separate endpoint (`/api/paper-method`). Replaying the recorded condition decisions through it reproduces the documents, verdicts and next actions of all 72 cases and 36 paired changes. | [`casepath_api/`](../casepath-api/casepath_api/); [parity record](../research/casepath/branch-benchmark/parity/PRODUCT_METHOD_PARITY_V5.json) |
| Study B controller and evidence planner | The method as evaluated in Study B: full process scope, timing and route choice. Preserved as an authored teaching record linked from About CasePath. | [`obligation_control/`](../casepath-api/casepath_api/obligation_control/) |
| Workbench and agent review | Product behaviour: source grounding, journaled state, correction and replay. It inherits none of the paper's measured results. | this folder, [`docs/AGENT_REVIEW.md`](../docs/AGENT_REVIEW.md) |

A live run of the Study A endpoint needs a model provider key and covers theft
claims only; the parity check replays recorded decisions offline.
