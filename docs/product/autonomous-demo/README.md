# Three fictional incoming claims

These packets are original synthetic inputs for the autonomous workspace. Every
person, address, signature, amount and event is invented. They contain no real
customer data, evaluator answers, model responses or instructions to publish
knowledge. Preparing this bundle made no provider request. It is not a live
acceptance receipt or a set of legally valid forms.

The three claims use the admitted lease-termination procedure. They provide a
small, inspectable sequence for initial qualification, a new evidence recipe,
and reuse with different case values.

| Packet | Supporting originals | Evidence introduced | Conditional check after the workflow settles |
| --- | --- | --- | --- |
| [01 · Lease baseline](01-lease-baseline/intake.json) | One tenancy agreement | Named parties, property and agreed tenancy terms | The agreement can support a `lease_contract` assessment and recipe. In a history with no qualified termination procedure, the first qualified definition is version 1. |
| [02 · Delivery refinement](02-delivery-refinement/intake.json) | Its own agreement and signed delivery record | Named recipient, delivery evidence and recorded delivery date | Reuse the qualified procedure; if independently supported, add the distinct `proof_of_receipt` recipe as the next version with exact parent hashes. The family-home branch introduces a separate spouse-notice gap. |
| [03 · Delivery reuse](03-delivery-reuse/intake.json) | A new agreement and a different delivery record | The same evidence fields, with different names, addresses, dates and amounts | Recheck these originals using the latest compatible version. Record actual recipe reuse; an unchanged reusable definition should not produce another version. |

The expected reusable ID is `procedure.lease_termination_dispute`, under
`policy-lease_termination_dispute-v1`. Version numbers depend on preserved
history. Inspect existing knowledge first; an already known recipe may mean no
new version is warranted. Never reset records or spending to manufacture a
version sequence.

## Native intake

Open the running local autonomous workspace at `http://127.0.0.1:4173/` and use
**Claims**. For each packet, in order:

1. Copy `title` from its `intake.json` into **Claim title**.
2. Paste that folder's `message.txt` into **Incoming message**.
3. Add only `tenancy-agreement.txt` and, for packets 02 and 03,
   `delivery-record.txt` as **Supporting files**.
4. Start the work once and observe its saved outcome before introducing the next
   packet. Inspect the source quotes, derived document requirements, recorded
   actions and knowledge lineage.

Do not upload `intake.json`, `manifest.json`, this guide or the message itself
as supporting documents. Native intake creates a browser operation key; another
submission is a new claim and can consume another pair of model requests.

`casepath/assets/autonomous-demo-packets.json` contains the same titles, messages
and original file bytes for a clearly labelled intake chooser. It omits API
idempotency keys. Choosing a fictional packet may prefill the form; it must not
start processing until native submission. Chooser wiring and browser acceptance
are separate from this prepared asset.

## API intake

Each `intake.json` is a complete body for
`POST /api/claim-loops/v1/autonomous/claims`, with `Content-Type: application/json`
and `X-CasePath-Agent-Work: 1`. Use the same loopback origin. The supporting files'
base64 values decode byte-for-byte to the adjacent `.txt` originals. Stable
idempotency keys permit recovery of the same API submission; do not change one
just to repeat a paid attempt after an unconfirmed response.

Read the returned claim through
`GET /api/claim-loops/v1/autonomous/claims/{claim_id}` and inspect
`GET /api/claim-loops/v1/autonomous/knowledge`. `manifest.json` records the input
hashes for local byte verification. It contains no expected model output.

## What counts as evidence

The agreement supplies the exact admitted field roster:
`contracting_parties`, `property`, `tenancy_terms`. The delivery record supplies
`recipient`, `delivery_evidence`, `delivery_date`. These identifiers describe
what to inspect; they are not answers inserted into the original sources.
Both evidence types are mandatory obligations in the current procedure.

The documents intentionally leave the termination notice, its form validity,
separate spouse service, statutory deadline calculation and legal outcome
unestablished. A carrier's sender-declared content description does not prove
what the notice says. Customer statements about arrears or prior disputes are
reports, not bank records or independent legal findings. A justified deferral
and an evidence request marked `prepared_not_sent` are appropriate outcomes.
No challenge, settlement, official filing or outbound message is authorized by
these files.

For a successful refinement/reuse demonstration, retain:

- The original-byte and extracted-text hashes, acquisition coverage and exact
  citation spans for each admitted document assessment.
- Separate interpreter and verifier receipts, including every proposed recipe's
  `knowledge:<document_type>` check, plus the accepted interpretation receipt.
- Qualified version 1 and its definition hash; version 2 with both parent hashes,
  `added_document_types` and the new recipe; the third claim's exact version-use
  receipt and `reused_evidence_recipes` count.
- Claim revisions, graph/checklist agreement, the explicit deferral and unchanged
  state after reload. Preserve any rejection or uncertainty instead of editing
  outputs to match this guide.

The provider may reject a mapping or recipe. That is a result to inspect, not a
reason to submit automatic retries. Merely receiving a category, compiling a
graph or seeing an animation does not establish refinement or successful reuse.

## Cost and current limits

Read `/api/claim-loops/v1/autonomous/status` before a live demonstration. The
configured profile shares the original lifetime limits of 18 provider requests
and USD 0.10, retaining all historical charges and unknown-cost reservations.
Each admitted workflow is limited to two independent model calls and USD 0.02.
These three cases can use six calls if every pair is admitted. They do not create
six fresh allowances. A 64,000-byte request guard, a 3,500-token output bound and
a 24-hour catalogue freshness gate can defer work without sending another call.
Unknown provider outcomes are never automatically resent.

No live-provider outcome, browser pass, knowledge version or accuracy claim is
asserted by this bundle. Read [the implementation contract](../AUTONOMOUS_WORKSPACE.md)
for the operating boundary and acceptance requirements.
