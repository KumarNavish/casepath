# The handler bar

**One goal.** casepath-pilot is genuinely useful to Protekta's employees, and using it produces the evidence that improves it.

**The loop every screen serves.**
autonomous work → effortless expert review → corrections propagate at once → measurable improvement

**The test.** A Protekta employee handles a real case with little effort, corrects the system with confidence, and has less work than before. Every interaction leaves evidence for the product and for research, and none of it is a separate task for the handler.

## Where we stand (Hackathon reference, 7 cases with a request letter)

| | start | now | target |
|---|---|---|---|
| Reference documents in CasePath's first request | 27 % | 73 % | ≥ 90 % |
| CasePath's requests that are in the reference | 73 % | 77 % | ≥ 80 % |

No later change may lower these. The numbers are re-scored model-free from stored runs after every change to process building.

## Ground rules

1. **One chain.** Process node → the facts it needs → the documents that show them → the next action. Nothing on a handler screen exists outside this chain, and every item says which node it is there for.
2. **One correction.** Whatever a handler changes (a node, a fact, a document, a deadline, the letter, the next action) is the same kind of event, applied the same way, undone the same way.
3. **No new model call for review, correction, propagation or measurement.** Evaluation is model-free; use it.
4. **Handler words, sourced statements, motion only on change, seven items at most, honest empty states.**
5. **Measure the system, not the person.** Exports carry a pseudonym per handler and no case content. The app says once, plainly, that use is measured to improve CasePath.
6. Case content never leaves Mobiliar. Nobody is notified. Code reaches GitLab only by a quiet push to the existing branch.

## L1 · One chain, visible in both directions

- Every document, fact, deadline and next action shows "wegen: «node»"; clicking goes to that node. Every node shows what it demands: its facts, its documents, the action it leads to.
- Changing a node (answering its question differently, skipping it, adding a step, changing its condition) re-evaluates everything downstream at once and shows the difference in one line: "Schritt 4 → 6 · 1 Unterlage neu · 1 nicht mehr nötig · Brief angepasst". The request letter and Braucht Ihr Urteil follow in the same moment.
- Done when: on a real dossier, one node change updates the checklist, the letter and the next action in under a second, survives reload, appears in the Fallbericht, and one undo restores the exact previous state.

## L2 · Correct anything, where it is

- Each artifact has its correction in place: a fact (value, optionally the sentence that shows it), a document ("liegt vor" with the file, "nicht nötig", "unbrauchbar"), a deadline, a node, the next action. The letter draft is edited in place before copying.
- A correction asks for its reason in one tap: a short list fitted to the artifact ("steht anders in den Akten", "für diesen Fall nicht relevant", "gilt generell", "fehlt in CasePath", "Formulierung") and an optional note. No reason, no extra step: the default is "ohne Angabe".
- The corrected item is marked "vom Bearbeiter gesetzt" with who and when, and its original stays one click away.
- Done when a handler can take a real case from open to "erledigt" without leaving the Übersicht except to read a source.

## L3 · Corrections become learning, safely

- A correction is stored as: what (artifact kind, before → after), why (reason, note), where in the process (node, legal basis), under which versions (workflow, Knowledge, code). Append-only.
- A correction with "gilt generell", or the same correction made in several cases, becomes a Knowledge proposal with its scope stated: this process, this node, this condition.
- **Before a proposal can be activated, it is replayed on all stored cases, model-free.** The reviewer sees its effect: how many earlier cases change, in what way, and what it does to the reference score. A proposal that lowers the score says so.
- Activation stays a person's act. Each active item shows how often it was applied, confirmed and corrected since.
- Done when a correction made on one Hackathon dossier, activated, visibly changes another dossier's requirements, and the replay predicted exactly that change.

## L4 · Testing is native

No questionnaires. The product records what happens anyway:

| Measure | From |
|---|---|
| Accepted unchanged, per artifact kind | items reviewed without a correction |
| Interventions per case, by kind and reason | corrections |
| Letter changed before use | size of the edit between draft and copied text, as a ratio |
| Active handling time | open to "erledigt", idle time excluded |
| Sources opened | which statements a handler checked |
| Same correction again | a correction an active Knowledge item should have prevented |
| Cost | minutes and tokens per run |

- An "Auswertung" page shows these per case and over time, with the reference scores on top. Its export is content-free, pseudonymous, and carries the parity manifest, so a result can be tied to the exact code, workflow and Knowledge versions.
- Improvement is the trend: interventions per case and "same correction again" falling as Knowledge grows, at equal or better reference scores.
- Done when the page is filled by ordinary use of three real cases, and its export passes the scorecard's content guard.

## L5 · End to end

- **A case continues.** When new files arrive, CasePath reads only those, moves the case along its process and proposes the next action; the handler sees what changed since last time.
- **Next actions beyond the first letter**, each as a draft in Protekta's form, each tied to its node.
- **Replay at the handler's decision points** (research and product in one): cut a Hackathon dossier at the moment Protekta acted, let CasePath work on what was in the file then, and compare its next action with what Protekta actually did. Start with the first request letter on three cases; extend only if the result is informative. Report tokens.

## Order

Reading fix (claim first, deadlines as a list) → L1 → L2 → L4's recording (so every later interaction is already measured) → L3 → L4's page → L5. Watching the run live stays as it is, with the five stages in handler words added when L1 is done.

## How each step ships

1. Audit what exists; build only the gap. `make test` ends "OK". Drive the whole flow on the preview, both languages, no console error.
2. GitHub, then a quiet GitLab push, then one deploy.
3. Check the step's "done when" on three real dossiers. Re-score the reference table.
4. Report in ten lines: what works on real dossiers, the numbers, and what a handler would still stumble over.
