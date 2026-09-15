# Agent review workflow

CasePath now exposes a persisted six-role review chain inside the same claim workbench. It is not a separate decision authority: every role reads through the existing CasePath authority, writes inspectable work events, and remains subordinate to the hash-chained claim journal and deterministic gates.

The visible sequence is:

1. **Facts** — reads the original packet and records exact source statements, not established facts.
2. **Orchestration** — verifies the upstream work identities and records checked handoffs.
3. **Source integrity** — rechecks quotations and source coverage.
4. **Process** — maps the admitted handling process, steps, and branches.
5. **Evidence** — maps obligations, document needs, and process links.
6. **Audit/readiness** — checks completion coverage, readiness, and the next action.

The browser presents this as **Agent review** on a claim and **Review team** across claims. The default trace is a causal milestone view; the full persisted event trace remains available through progressive disclosure.

## Default and external workers

`./bin/casepath dev` remains deterministic and provider-free. The normal launcher removes provider credentials and uses the reference Facts worker, so ordinary local use requires no model account or network inference.

An external model can replace **Facts only** through the same source tools, event store, gates, handoffs, and UI. This is an explicit developer/acceptance path, not an automatic fallback. Server configuration requires:

- `CASEPATH_AGENT_WORK_EXTERNAL_FACTS=1`;
- a regular, hash-bound OpenRouter catalogue snapshot in `CASEPATH_AGENT_WORK_CATALOGUE` fetched within the preceding 24 hours;
- a server-side `OPENROUTER_API_KEY`.

A start request must also explicitly select `facts_worker: "external_facts"`. Configuration failure rejects the external choice rather than silently substituting a different worker.

The current OpenRouter adapter is deliberately bounded to at most 6 provider requests, 20 tool calls, 800 output tokens per request, a 24 KB request body, a 45-second request timeout, and a USD 0.02 total reservation. Unknown provider outcomes are not automatically resent.

## Accepted end-to-end behavior

On 15 September 2026 the actual installed application, not a fixture authority, passed a fresh reference acceptance covering:

- all **150** claim workbenches;
- all **207** original source files, including **57** attachments;
- one complete six-role review with **265 persisted work events**;
- the existing source-linked evidence registration, replanning, correction, and reload path;
- rejection of malformed browser requests that attempted to bypass the work contract;
- desktop, laptop, tablet, and 390-pixel mobile accessibility/layout checks.

A separate real OpenRouter acceptance replaced only Facts with `cohere/north-mini-code:free`. It completed through the same source tools and deterministic gates with **6 genuine provider responses**. A later restart with no provider credential reconstructed the exact saved claim state and recorded work without another model call.

These checks establish the product's agent-work mechanics, provenance, persistence, recovery, and one bounded external-worker substitution. They do **not** establish legal correctness, general model competence, production readiness, or fitness for real claims.