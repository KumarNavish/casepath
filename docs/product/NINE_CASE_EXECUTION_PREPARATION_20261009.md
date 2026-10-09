# Pending nine-case execution preparation

This is a proposed preparation contract, not an authorization or an active allowance. The current production ledger remains unchanged and exhausted at 24 physical provider calls. No paid request or allowance mutation is authorized by this file.

The first zero-inference request preflight uses canonical adapter commit `862c6d194411b4626bb7ea2148aeb9496ec8c9e1`. All nine interpretation requests fit the configured 64,000-byte ceiling, with serialized sizes 41,101–55,332 bytes before current or future qualified knowledge is added. This is request size, not measured token use. Their conservative interpretation reservations total USD 0.067512750. Adding nine admissible verifier ceilings gives USD 0.155262750. Exact verifier inputs depend on future model outputs and knowledge compilation; this is not a claim that all future requests fit.

Fresh production readback at 2026-10-09 15:18:04 UTC records actual USD 0.0310427625, historical reserved USD 0.0028000, remaining USD 0.0661572375 under the existing aggregate USD 0.10 ceiling. The configured model is `openai/gpt-6-luna`; its checked conservative prompt reservation price is USD 0.000000125 per serialized request byte, completion price USD 0.0000005 per allowed output token, maximum 3,500 output tokens and two calls per workflow. These are the existing ledger reservation rules, not actual provider billing units.

Preparation may implement and test an inactive, explicitly applied nine-original grant. It must have no public grant endpoint, implicit activation, startup allowance, automatic provider retry, or production effect. Use only isolated temporary journals and MockHrana/mock-provider tests. Any real application requires a separate direct human approval and exact current-ledger compare-and-swap.

Two reviewable monetary options remain proposals:

- Keep the USD 0.10 aggregate ceiling and add only the bounded 18-call capacity: completion of all nine remains conditional on actual cost and full workflow reservation availability.
- Permit at most USD 0.18 of new workflow reservations, USD 0.02 each, with an effective aggregate ceiling no higher than USD 0.22. This covers the nine workflow maxima plus all currently recorded charges and reserves (USD 0.2138427625 in total). At the frozen configured prices, eighteen maximally sized admissible requests have a reservation ceiling of USD 0.1755. This option needs explicit approval of both call capacity and the monetary extension.

The implementation must preserve the old base policy and all old grants byte-for-byte, expose any effective ceiling separately, and bind the nine eligible original identities and source rosters. No other case receives this capacity. A failed or unknown workflow consumes its slot; do not reset or reassign it. The user approval reference, chosen monetary limit, preflight identity and prior ledger identity belong in the new immutable receipt.

The remainder is the earlier read-only accounting design. Its unchanged-USD-0.10 recommendation describes the first option; it does not prohibit presenting the second bounded option for human approval.

---

# Nine original cases: allowance plan

Read-only design, 9 October 2026. No allowance, code, Git, database, model, service, credential or deployment action was performed. Only this planning note was written. Explicit user approval is required before an allowance extension or paid execution. The adopted brief prohibits adding spending, resetting counters or bypassing unavailable allowance (`docs/product/UNIFIED_PRODUCT_BRIEF_20261009.md:111-113`).

## Verified starting point

- Inspected source: `80939f0ec4430402b029a646d60f5bf8b465e9f8`, branch `codex/casepath-causal-experience-integration-20261009`, clean checkout. No fetch was performed by this read-only worker. The path name still says `casepath-sites-hosting-20261009`.
- The continuity manifest passes its three hashes. It is an older research projection, explicitly non-authorizing; this product plan creates no research permission or writer lease.
- Saved live readback: `goal-live-budget-readback.json`, observed `2026-10-09T14:52:01.702Z`. Calls `24/24`; autonomous workflows `8`; autonomous calls `15`; previous grant workflows `3/3`, calls `6/6`; no in-flight request. Actual USD `0.0310427625`, reserved USD `0.0028000`, remaining USD `0.0661572375`; aggregate ceiling USD `0.10`; workflow maximum USD `0.02`; one historical unknown; no automatic retry. This is a supplied saved receipt, not a fresh production query by this worker.
- Selection file SHA256: `7d70edaf6e886ace18ea55f6b41ab3e44dd5760431bcf8f844ee47ab30b9537e`. Corpus `synthetic-150` manifest file SHA256: `7c885d3fd112dfc7314719d661fa73449f72b7bdf5b83159da9fa3e0b9a1b7eb`. All 35 referenced original claim/message/projection/attachment files match their selection hashes. This verifies bytes, not interpretation or successful execution.

Allowed original IDs, in selected order:

`clm_e262801f9368bc12`, `clm_521c20913f4e0f9b`, `clm_ee29ac770b1bf7b9`, `clm_f69b1747447bc221`, `clm_0c5e7c7723a3c694`, `clm_2a9c260c26afaa34`, `clm_c44ddc0914ba9298`, `clm_7dbd7c7d1c4ddf90`, `clm_9a179a4481767d43`.

## Existing mechanisms cannot reopen this allowance

`agent_work/store.py:109-124` creates an immutable singleton capacity-grant table. Its validator (`509-546`) requires exactly three workflows/six calls and a prior 18-call ceiling. `grant_three_autonomous_workflows` (`575-607`) returns the same approved idempotent receipt or rejects a different approval; it cannot create a second grant. Editing that row, replaying the CLI, restarting, reactivating policy, configuring another budget, or migrating a stale local database would violate the ledger's boundary.

The old usage validator (`549-572`) treats every post-grant workflow as belonging to that grant. A new grant cannot simply add 18 to the ceiling: without explicit epoch partitioning, the first additional workflow would exceed the already-used three-workflow grant. The local launcher also assumes effective ceilings are only 18 or 24 and checks totals against the old grant (`casepath/tools/run_agent_demo.py:168-225,458-526`).

## Smallest auditable extension, if approved

Add one separate immutable singleton receipt with a new versioned contract, for example `casepath.original-nine-capacity-grant/1.0.0`. Keep the existing base policy, activation, external-run grant and three-workflow grant byte-identical. This is one fixed original-case authorization, not a general grant service or arbitrary configurable allowance.

The receipt records exactly nine eligible originals and at most 18 additional physical calls. Bind it to the previous grant SHA256, base/activation hashes, exact current budget digest, all eight prior workflow seals plus call/outcome/terminal seals, source commit, selection and corpus hashes, the nine canonical binding hashes, rule-set hash, frozen provider/model configuration and preflight digest. Record the actual human approval reference, actor, reason, UTC time and idempotency key. Hashes establish identity; an actor string or checksum does not supply approval.

Construct eligible identities from the canonical original-corpus resolver and the committed original intake/source descriptors. Freeze each original ID, original binding, descriptor-roster hash and derived workflow ID. `begin_autonomous_call` must match that approved identity before reserving a new call. Enforce one new workflow per eligible original, two stages (`interpret`, `verify`), and at most nine workflows/18 calls across the receipt. New evidence, changed sources/rules, arbitrary uploads, copied demo packets, changed original identity, a different model, or a second workflow for the same original receive no capacity from this grant. Selection reasons, labels and visual observations stay outside semantic inputs.

Partition validation into the pre-existing epoch, the old three-workflow epoch, and this exact nine-case epoch. Every prior workflow/call remains in its original epoch; new workflows reference the new receipt, never the old one. Preserve old accounting and exact replay before checking new admission. Effective lifetime calls become at most `42` while base `max_provider_calls` remains `18`; expose separate old/new grant identities and counters. Do not loosen old 3/6 validators globally.

Use the existing shared `WorkStore` transaction/reserve-before-send path for SQLite and the hosted connection factory. Add no provider adapter, retry path, browser approval button or public grant endpoint. A bounded operator command must explicitly target the remote primary through the existing hosted factory after authorization; the old local launcher operates on a stale local ledger after cutover and must not apply this grant. Update launcher receipt/readback validation for the new receipt, while keeping the local paid writer stopped.

## Dollars, sequencing and preflight

Permission for up to nine sequential workflows is not a guarantee all nine finish. Nine full USD `0.02` ceilings total USD `0.18`, exceeding the remaining USD `0.0661572375`. The existing grant demands three full ceilings fit (USD `0.06`); copying that predicate for nine cannot pass. Preserve USD `0.02` as the maximum, actual/reserved historical costs, and the aggregate USD `0.10` ceiling. Do not invent a lower cost estimate or release the historical unknown reserve.

Before the final approval request, prepare a real deterministic preflight using the product's canonical bindings, actual extraction/context/request construction, closed schemas and frozen public provider/model prices. It must send no inference, publish no knowledge, modify no production state and read no credentials. Capture interpretation request bytes and a conservative verification envelope including the largest admissible compiled proposal and knowledge context. Check existing byte/context/output limits. Compute each call bound with the existing formula: `prompt_price × request_bytes + completion_price × max_output_tokens + request_price`; show all nine two-stage bounds and the current ledger snapshot. Reject model/config/price/source changes before dispatch. A verification request depends on the eventual interpretation, so its preflight is an upper bound, never a fabricated future output.

If those upper bounds cannot justify all nine under the ceiling, retain an explicitly conditional sequential authorization and truthful dollar admission stops; do not claim a guaranteed nine-case result. Even with fitting bounds, the unchanged admission path requires USD `0.02` available at each fresh workflow start and reserves that full amount until terminal. Report whether the ninth-start condition can be guaranteed; do not silently lower reservations to make it pass. Any tighter per-case subcaps or revised reservation policy would be a separately reviewable change. A rejected/unknown workflow consumes its original slot; unused calls cannot be reassigned or automatically retried.

Retain the single inference slot and hosted generation fence. Grant creation requires an exact budget compare-and-swap, no active legacy work, all prior autonomous workflows terminal, and no pending provider effect. The historical unknown remains reserved but is not in-flight in the supplied receipt. A new autonomous unknown blocks further inference; ambiguous grant/reservation commits require readback against the same idempotency identity before any send. Never regenerate a request identity to bypass that state.

## Acceptance evidence and migration limits

Use isolated temporary SQLite and the existing MockHrana/mock-provider fixtures only. Necessary checks: old rows and seals unchanged after additive schema/grant creation; old/new epoch accounting; same approval concurrent replay exactly once; stale/different approval rejected; nine exact originals admitted and tenth/duplicate/changed-source/wrong-corpus cases rejected before reservation; at most 18 sends; rejection/unknown consumes a slot without replacement; USD `0.10` aggregate and USD `0.02` workflow limits; serial pending slot; restart/replay/navigation add no calls; changed prices/config refuse admission; dropped or resealed-invalid ancestry fails closed; lost hosted commit acknowledgement causes zero sends; lost ownership fences writes. Existing relevant suites are `test_autonomous_budget_v1.py`, `test_autonomous_budget_grant_v1.py`, `test_agent_demo_launcher.py`, and hosted storage/SQL/lease/recovery/migration tests. This audit ran no suites and makes no claim that the proposed extension passes them.

The schema must be additive with immutable update/delete/replace triggers and transaction-scoped prefetch for the new table. Production migration/readback must preserve every old row and original source hash; the existing migration tool cannot replenish allowance. Older binaries will fail closed once new-grant workflows exist because their roster validator knows only the first grant. Drain old deployments before use, and do not roll back to older code or a pre-cutover ledger without exporting and reconciling the current remote ledger. Keep the legacy `/proc/1/maps` migration audit fail-closed where unsupported.

Stop condition: a reviewed dry-run/preflight packet and a concrete approval request for these nine originals, up to 18 calls, no retries, unchanged dollar maxima and conditional completion. No grant or live run is authorized by this note.
