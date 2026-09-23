# CasePath product audit — 23 September 2026

Audited the local deterministic `synthetic-150` application at `ba24aa5`. The journey used `clm_a62c178195d21648` for a completed review and `clm_731b214dde882f89` for a message, photo, review, and rejected evidence check. These are product observations, not research results. Screenshots are in the task's `casepath-audit` folder.

## Journey and screenshots

1. Queue: `01-queue.png`. Clean list, but five visible rows have the same next step before review.
2. Open claim and read message: `02-open-claim.png`. The original packet is accessible beside the review action.
3. Start review: `03-running-review.png`. The main workspace shows a disabled status button while saved work advances elsewhere.
4. Completed review and next action: `04-completed-decision.png`. Process, action, and justification are visible, but the actual evidence gap and source support are below the first viewport.
5. Evidence: `05-evidence.png`. One current requirement is clear; nine conditional requirements are collapsed.
6. Select requirement: `06-evidence-selected.png`. The source rail changes to a generic explanation, hiding the customer message. The action rail does not react.
7. Process: `07-process.png`. Current and later steps are distinguishable; branches repeat the generic label “Conditional path.”
8. Work log: `08-work-log.png`. The default summary leads with six workers and 268 actions rather than what sources and facts were checked.
9. Second claim and photo packet: `09-packet-with-attachment.png`, `10-attachment-inspection.png`. Exact original image preview works.
10. Rejected evidence check: `11-evidence-not-accepted.png`. The product correctly keeps the requirement open, but does not show what the photo established or why it fell short.
11. 390px claim workspace: `12-mobile-390.png`. The action moves ahead of the process and there is no horizontal overflow; “See reason” still requires a separate jump.
12. 390px and desktop corpus: `13-data-explorer.png`, `14-data-desktop.png`. Search, language, file filtering, and packet reading work. The overview lacks the released family and domain structure.

## Findings

| # | Problem | Evidence | Change |
| --- | --- | --- | --- |
| 1 | The justification is static and fragmented. Selection changes one pane without connecting the action, evidence need, process step, and original source. | Steps 4–7; `canvasTrace`, `evidenceSource`, and `showEvidenceSource` govern these rendered surfaces. | Make “Why this?” a coordinated reasoning lens. Keep the action visible, select the relevant requirement and process node, and reveal the original source status or exact accepted passage. Preserve the distinction between source review and accepted evidence. |
| 2 | Review progress and work history foreground role architecture over the work performed. | Steps 3 and 8. The queue exposes a stage count, while the main view offers only “Agent review in progress”; the work log shows role and action counts. | Show saved work stages in the main journey, with actual source, process, evidence, and action outcomes. Keep role identity and full trace on demand. |
| 3 | The corpus browser explains packet contents but omits its family and domain structure. | Steps 11–12; `corpus.html` and its live packet browser. | Add authoritative domain/family counts and a compact distribution view derived only from observable intake metadata. |

## Design contract for the first implementation pass

Use the current three-part workspace and its white, deep-blue, and warm-attention palette. Put a short “Why this?” control next to the current action. When selected, the action-to-source chain should fit in the visible rail, distinguish missing from received evidence, and offer direct navigation to each linked object. Selecting an evidence need or process node should update the same chain. No unsaved inference, model activity, customer dispatch, or source acceptance is implied by the lens.

Keyboard focus, visible selected states, 390px and 320px layouts, and reduced motion are part of this interaction. The audit does not establish screen-reader compliance, legal correctness, or a suitable document request in either reviewed claim.

## Implemented journey and verification

The final reasoning lens occupies the center of the workbench while the action stays visible beside it. This gives the full source-to-action chain room to read at desktop width. Selecting a requirement, process step, or exact passage changes the corresponding source view. The saved review now leads with packet, facts, process, requirements, evidence, and action outcomes; role handoffs and the full trace remain inspectable. The data page shows only published aggregate corpus counts and retains its original packet browser.

The representative journey is `clm_f69b1747447bc221`, a shipped synthetic packet with a customer message and two original notice PDFs. A fresh local review saved six role receipts, ten unknown facts, and one current evidence requirement. **Why this?** showed the missing original passage, required fact, process obligation, and policy support. The first **Check & register evidence** action recorded a passage from the original message and advanced the active step from “Capture issuer, receipt and end date” to “Preserve challenge or extension deadline.” The second action recorded a passage but left that new requirement insufficient. The workbench distinguished both outcomes, and the current action and trace survived reload. Nothing was sent or settled. This is a product demonstration, not a legal or benchmark result.

The first disposable audit clone exposed a real boot validation defect after a rejected evidence proposal: its journal contained `EVIDENCE_PROPOSAL_REJECTED`, which the boot validator omitted from its permitted event list. The new validator includes that event and `NATIVE_PROPOSAL_REVISION_RECORDED`, both present in the claim-loop contract. It verified all 158 existing journal events in the untouched audit clone. The QA clone's claim replay also returned `journal_verified: true`. The original audit clone remains preserved for inspection.

Visual passes: desktop reasoning and work log (`19`, `23`), corpus desktop and mobile (`15`, `18`), reasoning at 390px and 320px (`21`, `22`). The claim had no document route, so the lens says “No customer document specified” rather than supplying one. Browser checks found no horizontal overflow at 1440px, 390px, or 320px.

The final browser pass also covered 1024px, keyboard activation and focus return, exact passage highlighting in the original message, mobile source-drawer Escape, and reduced-motion emulation. During a stopped local service, the visible claim stayed in place, explained the unavailable service, and offered **Try again**. Restarting the service and selecting that control restored the latest saved claim without changing the active action. One launcher attempt timed out during its post-ready probe; the next sealed launch completed. After the full suite, an unowned `_virtualenv` bytecode cache appeared in the attested virtual environment and blocked launch until those two generated cache paths were removed. This environment limitation remains separate from the claim journal and should be checked during release preparation.
