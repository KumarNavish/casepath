# Claims journey UI release

This change improves the existing claims workspace; it does not introduce a second workflow controller or change claim authority.

## Using the workspace

The queue puts status, blocker, next action and handler next to each claim. Search and filters remain in the URL so opening a claim, reloading and going back preserve the same view. Queue shortcuts select existing API filters. Failed refreshes retain the last loaded records and identify them as stale.

The claim workbench keeps one next action prominent, with the current process and evidence underneath and the original message beside it. Open an evidence item or process step to inspect its source passage, supporting process rules and consequence. Conditional evidence stays separate from requests that are needed now.

Accepted evidence displays a before/after summary: which requirement changed, which request is no longer current, which requirement becomes active, and the resulting readiness. A rejected source never appears as an accepted observation. Corrections require a preview and confirmation, retain their recorded scope and show that unrelated facts were preserved. There is no destructive undo: restoring a finding requires accepted evidence and does not erase history.

Original text is keyboard accessible. PDF attachments are verified against their recorded bytes and open in the browser's full PDF viewer in a separate tab; the claim stays open. This intentionally replaces a sandboxed embedded viewer that produced a browser error. Source hashes and locators remain available on demand.

## Authority and validation boundaries

All mutations still use the existing claim-loop endpoints, expected revisions and exact idempotency keys. The new presentation module only renders validated responses. The queue is scoped to the **60 public synthetic development claims** in this standalone repository; the 90 reserved research inputs are not included.

Local deterministic execution demonstrates product mechanics, not model competence, legal correctness, production readiness or real-world outcomes. A proposed plan remains explicitly provisional. Readiness does not authorize approval, payment or closure. This release does not enable inference or dispatch to customers.

## Regression commands

Run `node --test casepath-qa/claims-workspace-presentation-v1.test.cjs` for presentation boundaries, followed by `./bin/casepath test` for the isolated backend and release suite. After authoring changes, follow `CONTRIBUTING.md` to update asset hashes and seal the source manifest before launching.

Browser evidence is delivered separately from application source. It covers the real queue, source inspection, assignment, assessment, evidence acquisition and replan, correction preview/cancel/apply, export, recovery, keyboard behavior, loading and error states, desktop and 390-pixel mobile layouts. Browser checks use an isolated journal and no provider calls.

## Provisional follow-up compatibility

Saved model-proposed follow-ups retain their audience and every requested item. They are marked as unsent proposals, not completed claims; an enabled follow-up cannot appear as fully covered readiness. The primary action opens the existing saved investigation rather than creating a second evidence controller or dispatching a request. The inner deterministic cycle's zero additional model calls must not conceal an earlier recorded provider call.

`node --test casepath-qa/native-proposal-presentation-v1.test.cjs` checks this boundary in the actual presentation renderer. The historical hosted-bundle regression builds only a temporary local fixture: it no longer assumes a hosting installation or a live project identifier in this standalone repository.
