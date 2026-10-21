# W4 — Cases

The customer's verbatim request leads each row. Domain and plain status sit in aligned columns; failed legal tests appear in amber just below the request. The existing search, domain/status filters, pagination and whole-row case link remain available. Completed rows open the Evidence desk at the recorded answer.

The API adds a read-only `customer_request` projection, extracted as an exact span of the original message. All 150 originals contain an explicit request. The projection never enters the engine state, binding or journal. Native messages without an explicit request retain their original title without quotation marks; older catalogs without the projection keep their original excerpt view.

Status uses recorded state: `Answer ready`, `Needs N documents`, or the existing plain state. An unknown state stays unknown. Failed legal tests retain their recorded predicate and the shared plain-language label. No conclusion is inferred from the request.

## Review frames

- [Cases](cases.png)
- [Answers ready and failed tests](answers-ready.png)
- [Search within the customer's request](request-search.png)

## Verification

The browser receipt checks the actual sealed bundle at 1440 × 900: all nine completed rows open their own answer, requests match original messages, failed tests retain their labels, domain filters and pagination work, search survives reload, and empty search is honest. Captured operation traces keep checks GET-only and deterministic. The focused tests cover all nine rows, missing documents and absent/unknown fields. Backend checks cover all 150 projections, unchanged state hashes, native journal immutability and full-text search.

No paid inference, original-nine rerun, hosted writes or deployment. The Mac-owned public read-only test is untouched. This branch follows approved W3-A `4fcf3e2`; W5 follows this handoff while the planner reviews, with change requests taking priority through `wait_for_planner.sh`.
