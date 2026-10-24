# Operator review: paired family-home notices

## Status and scope

The engineering demonstration uses original synthetic intake cases and explicitly records its automated actor as **Test handler**. Those events prove the editing, preview, journal, versioning and reuse mechanics. They do not establish qualified human approval.

The proposal below is ready for source review. Its substantive appropriateness, applicability and completion criterion remain for a qualified reviewer to decide. Process review does not authorise a claim outcome.

## Open the two cases

Use the local operator workspace after starting the normal CasePath launcher:

- [Earlier case — Foster](http://127.0.0.1:4173/?journey=review&view=northstar#claim=clm_f69b1747447bc221)
- [Later case — Miller / Morgan](http://127.0.0.1:4173/?journey=review&view=northstar#claim=clm_0e538990cc6ba7ef)

The public demonstration remains read-only. The operator route is a local review workflow.

| Source fact | Earlier case | Later case |
| --- | --- | --- |
| Claim | `clm_f69b1747447bc221` | `clm_0e538990cc6ba7ef` |
| Original intake, Europe/Zurich | 26 August 2025, 12:00 | 31 August 2025, 13:00 |
| Tenant notice | Robin Foster; **30. Juni**; two supplied pages | Avery Miller; **30. Juni**; two supplied pages |
| Spouse notice | Casey Foster; **31. Juli**; one supplied page | Avery Morgan; **31. Juli**; one supplied page |
| Property | Zollikerstrasse 56 | Zollikerstrasse 19 |
| Remaining uncertainty | Intended end date, receipt evidence and completeness of the documents actually served | Its own corresponding uncertainties |

Both spouse PDFs refer to a second page as part of the official form. Both customer accounts say that page two is missing from the scan and that they do not know whether only the copy is incomplete.

This establishes differing printed end dates and incomplete supplied scans. It does not establish which date governs, verified calendar receipt dates, completeness of the served originals, or invalidity of a notice.

## Exact original documents

The source files and their hashes come from the original synthetic-150 manifest. No source bytes were changed.

| Source | Original file | SHA-256 |
| --- | --- | --- |
| Foster tenant | [Tenant notice](../../casepath-api/casepath_api/corpora/synthetic-150/artifacts/clm_f69b1747447bc221/01-6fec533be661-01-Tenant_termination_notice_June_Robin-Foster.pdf) | `6fec533be661db939f8b62b272d7195a4a4b5d13ed7e22bdf53425019e096253` |
| Foster spouse | [Spouse notice](../../casepath-api/casepath_api/corpora/synthetic-150/artifacts/clm_f69b1747447bc221/02-6788e6ce28d0-02-Spouse_termination_notice_July_Robin-Foster.pdf) | `6788e6ce28d07f65b59e4b04ceb2e765c7458287ded3e06c70d7392e5ae0094f` |
| Miller tenant | [Tenant notice](../../casepath-api/casepath_api/corpora/synthetic-150/artifacts/clm_0e538990cc6ba7ef/01-cdfe37ad8f68-01-Tenant_termination_notice_June_Avery-Miller.pdf) | `cdfe37ad8f68550d7e69c468a3753d368695a332d119711d53ed91489b7213d0` |
| Morgan spouse | [Spouse notice](../../casepath-api/casepath_api/corpora/synthetic-150/artifacts/clm_0e538990cc6ba7ef/02-08f3ca5d9ba3-02-Spouse_termination_notice_July_Avery-Miller.pdf) | `08f3ca5d9ba345447ff74c1d026644558401bddc19626cfb12bcd0d3be5cb584` |

The source API is `/api/claim-loops/v1/workspace/claims/{claim_id}/artifacts/{artifact_id}`. The four corresponding artifact IDs are `doc_0d043bd02b074535`, `doc_b137c2a1c0239f90`, `doc_ee5afc3a4e3cd60f` and `doc_7377764332dadd26`. The original intake IDs are `com_a061e0da3423e37c` and `com_cebc16bebc169805`.

## Proposed structural correction

Add **Compare both complete notices**, conditioned on the recorded family-home fact, using the tenant notice and separate spouse notice as its document context. In the engineering demonstration it follows deadline preservation and adds a `requires` connection to **Prepare challenge, extension or settlement** (`lt_resolution`).

The proposed comparison should record the addressee and printed end date on each notice, whether the supplied copies are complete, what remains unknown about the served originals, the receipt evidence for each spouse, and the reviewer's finding and handling consequence.

The reviewer must decide exactly what permits completion, especially when a discrepancy remains unresolved. The reviewer must also decide whether this placement preserves necessary protective action and whether the rule is appropriate across family-home cases. Do not infer that a missing scan page or inconsistent date establishes invalidity.

The existing software already recognises the date discrepancy and asks for complete copies and receipt dates. The proposal makes the comparison an explicit, reusable process prerequisite.

## What the actual engineering preview establishes

The receiving resolution step is already blocked and remains blocked. The added prerequisite changes its process dependency. The next action remains **Preserve challenge or extension deadline**.

The two notices become associated with the added comparison step. Their existing request timing and held-file review state remain unchanged. The receiving claim retains its own facts, source files and evidence reviews. No earlier-case completion or source sufficiency is transferred.

The original evidence connection remains in the graph. Current evaluator diagnostics give explicit required blockers precedence in the displayed blocker list; completing only the new prerequisite still cannot bypass the incomplete evidence predecessor. A regression tests that execution rule without changing historical evaluator or journal hashes.

A saved fragment is pinned by ID, version, content hash and source claim. Applying it imports a reviewable boundary connection. Publishing version 2 does not silently move a receiving claim pinned to version 1.

## Qualified review question

> After reviewing both source pairs and the exact impact previews, do you approve this comparison as a prerequisite for completing resolution preparation in family-home cases, including its completion criterion and preservation of necessary deadline-protection work, and approve saving this exact fragment for reuse? Record your name, review role and approval with a reason, or identify the specific change required.

The answer must be tied to the actual version and preview being reviewed. Preserve the Test handler engineering history. Do not rename it or retrospectively describe it as human approval. A typed actor name is an audit annotation; the application does not authenticate professional qualifications.

If the fragment changes, review the changed version before describing it as expert-reviewed.
