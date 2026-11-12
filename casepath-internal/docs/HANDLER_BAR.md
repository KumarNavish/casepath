# The handler bar

**One goal.** casepath-pilot is genuinely useful to Protekta's employees, and using it produces the evidence that improves it.

**The loop every screen serves.**
autonomous work → effortless expert review → corrections propagate at once → measurable improvement

**The test.** A Protekta employee handles a real case with little effort, corrects the system with confidence, and has less work than before. Every interaction leaves evidence for the product and for research, and none of it is a separate task for the handler.

## Scoreboard (7 development dossiers, cut just before Protekta's first request)

Study cases D2, D4, D7 and reserve D5 are sealed and take no part. Item labels by the Mac bridge, from the cut files.

| Measure | Baseline (975aa9ef) | Round 1 (ec2c2cae) | Target |
|---|---|---|---|
| Routing: right process | 6/7 | 7/7 | 7/7 |
| Asserted and right: facts | 23/24 | 32/32 | ≥ 98 % |
| Asserted and right: document statuses | 40/41 | 45/45 | ≥ 98 % |
| Wrong on a fact that decides the path | 1 | 0 | 0 |
| Stated in the file but left open | 19 of 43 (44 %) | ≈ 6 (≈ 14 %) | ≤ 10 % |
| First request: Protekta's documents asked now | 14/22 (64 %) | 18/22 (82 %) | ≥ 90 % |
| First request: asked now or "später evtl. nötig" | 19/22 | 22/22 | |
| First request: accuracy (a part of a requested whole is neither extra nor hit) | 14/17 (82 %) | 18/22 (82 %) | ≥ 90 % |
| Next action of the same kind as Protekta's | 7/7 | 7/7 | 7/7 |
| Corrections needed (one per wrong or missing item) | 32 | ≈ 14 | halve each round |
| Cost: non-cached tokens, all 7 runs | 1.31 M | 1.29 M | no rise |

**Handler workflow, night of 2026-11-11/12 (round 3, a5247e55, live from 19ba29bc).** First request, named rule (a document named as its own line or inside a ticked line counts as asked): 20/22; strict own-line count 17/22 (D1's expert report now offered with "erwähnt, lag nicht bei"). Extras 3 after the disputed-finding rule (D3 Mietzinszahlungen, D8 correspondence exception, D9 Kaufbelege). Cold, new upload: D11 160 s, D3 245 s, D10 154 s, D1 cut 200 s; re-run median 154 s, 18 calls, 79k non-cached, 20k output (target for a small case: under 120 s and 60k). Next action against Protekta's at its decision point: A2 (D3, phone note read as evidence) pass; A6 (D3) pass, date 12.04.2024 = Protekta's; A7 (D11) pass on kind and reason, date 14.02.2025 = Protekta's after the as_of fix.

**Steering: what it does, and what has only been run against the scripted team (never against the real model).**
- Live: the run line on the Übersicht (stages, time, current file and page), historic cases marked "Stand am".
- Scripted only: Anhalten (stop before the next turn, keep brief, facts, documents, usage); Weiter (continue, finished steps skipped, same result as straight through); Verwerfen (back to the last finished result); a case worker's answer during a run or a pause, honoured from the next turn and never overwritten; anderer Prozess while paused or from the run line (Anhalten, choose, Weiter); the chosen process announced before any agent reads. A continued run carries the paused run's usage and is counted once, outside the timing profile.
- First real check, when tokens are allowed: one gate run with Anhalten after the reading, then Weiter.

**Audit against HANDLER_WORK** (2026-11-12; "yes" only with a named test or check; scripted means never run against the real model).

| Point / action | Built | Proof | Missing |
|---|---|---|---|
| 1 Centre is the prepared action | yes | `deploy/preview/check_fold.mjs` (first card, title 120–144 px; measured at one window size, 1428×811, the runtime ignores other sizes); `test_a_case_on_the_handler_workflow_carries_its_draft_and_its_file_note` | a run at 1280×720 in a browser that can set it |
| 2 Reasons as a chain | yes | `deploy/preview/check_sources.mjs` (every checklist line opens its source or rule, every "weil" fact opens its source: 4 of 4 on the synthetic case); `test_edits_change_the_checklist_and_can_be_undone` | the same check on a handler-workflow case (more lines, "Deckung offen") |
| 3 Feedback is finishing the work | partly | `test_andere_handlung_changes_the_draft_and_the_date_and_is_logged_with_its_reason` (another action: draft, date, item.corrected with reason); local walk 8/8; `check_add_document.mjs` (2 actions) | a browser count for "andere Handlung" (the preview's synthetic workflow has no stage actions) |
| 4 A case has a next date | yes | `python -m casepath.process.clock` self-test; `test_a_case_on_the_handler_workflow_carries_its_draft_and_its_file_note` (next date: deadline before follow-up); A6/A7 letters use the same date (`test_every_action_kind_renders_its_form_with_every_part_and_no_empty_placeholder`) | — |
| 5 Arrival | partly | `test_a_new_file_is_announced_and_a_second_preparation_shows_what_changed` | the run starts only when a person asks (deliberately: it spends tokens); a re-run reads all files, not only the new ones |
| 6 The file note writes itself | yes | `test_the_file_note_is_the_same_paragraph_every_time` (text pinned); `test_a_document_the_handler_unticked_is_neither_asked_nor_awaited` | — |
| A0 Receipt | no | — | Protekta's online form sends it; not CasePath's |
| A1 First request | yes | form: `test_every_action_kind_renders_…`; stage: `test_the_stage_follows_what_was_done_what_arrived_and_the_handlers_cover_decision`; live: 20/22 named on the seven cuts | —; the screen shows the server's letter for every kind (parity proven in bd96d907, browser letter code removed in 415a8f33) |
| A2 Phone note | partly | read as evidence: D3 decision point, scored model-free (pass); A6 after a call: `test_the_stage_follows_…` | kein Entwurf: the note is written by the handler ("Telefonnotiz erfassen") |
| A3 Upload link | no | — | kein Entwurf: the link comes from Protekta's upload system |
| A4 Question back | yes | rule: `test_the_stage_follows_what_was_done_what_arrived_and_the_handlers_cover_decision` (one open point → A4 with that question; two → not); form: `test_every_action_kind_renders_…` | a decision-point test on a dossier |
| A5 Assessment | partly | form: `test_every_action_kind_renders_…`; stage "beurteilen" carries A5 | a marked gap where only the handler can write (`test_what_only_the_reading_or_the_handler_can_say_is_a_marked_gap_never_an_invented_sentence`); decision-point test (D11, planned, needs tokens) |
| A6 Pending with a deadline | yes | form and date: `test_every_action_kind_renders_…`; `test_the_stage_follows_…` (after a call); live: D3 decision point, date = Protekta's | — |
| A7 Status inquiry | yes | form: `test_every_action_kind_renders_…`; clock: `test_the_stage_follows_…` (silence after A5); live: D11 decision point, kind and reason, date = Protekta's after the as_of fix | — |
| A8 Letter to the other side | partly | form (draft to the customer first in its addressee line): `test_every_action_kind_renders_…`; stage "gegenpartei" | a marked gap where only the handler can write (`test_what_only_the_reading_or_the_handler_can_say_is_a_marked_gap_never_an_invented_sentence`); decision-point test (D6, planned) |
| A9 Negotiation | no | — | kein Entwurf: the stance is the handler's; no tracking of offers |
| A10 Mandate | partly | form: `test_every_action_kind_renders_…`; stage "mandat" | decision-point test (D9, planned) |
| A11 Payment | partly | stage "abwicklung" carries A11 | kein Entwurf: amount and date come from the payment system; decision-point tests (D1, planned) |
| A12 Closing | partly | form: `test_every_action_kind_renders_…`; clock: A7 then 14 days → A12 (`casepath.process.clock` self-test covers the rule's shape) | decision-point test (D9, planned) |

**Action tests start from the handler's decisions.** Stages after "Deckung" and "Vorgehen" are reached only through the handler's own decisions (handler_only facts the agents never set). A test of A5, A8/A9, A10, A11 or A12 therefore sets those decisions on the cut first, as set_fact edits, as the handler had decided by then; the test then measures the next action from there.

**Named in the scores.**
- D8: 1 extra from the all-of rule ("Sämtliche Korrespondenz"), accepted: Protekta asked for it in 6 of 7 letters.
- D6: the round-1 run judged five undated photos from one moment "unbrauchbar" (the need asks for photos over the whole period); the baseline run had them "vorhanden". Judged against the need, round 1 is right and the baseline status is the one wrong document status; Protekta did not ask for photos in D6, so the letter asks one document more than Protekta did.
- D10: "seit 5 Jahren" in a 2024 e-mail is kept as a stated period ("5 years before …"); the year is shown as berechnet and not counted as an established fact.
- "Left open" is approximate in round 1: the process builder's own questions differ between runs, so items whose question was not asked are counted neither way.

**Defaults follow practice.** A line's default is the one that needs fewer handler changes in practice. Named exceptions: D8 (all correspondence asked, practice 6 of 7); D10 (Protekta asked "allfällige weitere Beweismittel" although photos were in the file; practice 4 of 5 the other way).

**Stage facts left open (from 2026-11-11).** Counted over the facts of the current stage the reader may set (klaeren: written notice, rent dispute, damages). Row: open · of which stated in the file (the reader's gap) · of which asked in the letter · neither. Handler-workflow cuts: 14 of 21 open; stated in the file 0, one borderline (notified, form not stated); no miss found by keyword search and reading the hits, a paraphrase could escape it. Round 1 is not comparable (other workflow, other stage facts).

**Question defaults follow practice.** Asked by Protekta when the file left it open: written notice 0 of 5, rent dispute 0 of 4, what the customer wants 0 of 5, so all three are offered unticked; "Seit wann" stays ticked (4 of 7).

**Round 2 list (with Dominik's points, one combined re-run before the freeze):** conditional needs whose condition the file states (D1 expert report, D8 rent payments, D9 and D11 receipts for damaged goods); ask for the rest of an all-of need only when the file refers to correspondence it does not hold; the seeded evidence need asks for more than Protekta does at intake ("über die ganze Dauer, Messprotokoll oder Fachbericht"), so a few undated photos fail it (D6): when a document is there but falls short, the letter asks for exactly what is short ("weitere Fotos über die Dauer oder ein Messprotokoll"), not for the document as if nothing existed; whether the need's bar is right is a question for Dominik's session. The brief carries the sentence of the claim report it took the customer's request from, so the Anliegen line has its source (until then it shows no chip).

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

## E · Fast and cheap, proven on a fresh case

**Today:** 5 to 9 minutes and about 0.18 M non-cached tokens per case (about 43 k of them output), whatever its size. **Target: a small case prepared in under 2 minutes and under 60 k non-cached tokens, with no scoreboard row worse on any case.** First useful line on screen within 20 seconds.

**Measure before changing anything.** From the stored runs, one table per phase (reading, routing, each agent, second reading, checking, result): model calls, seconds, input, cached, written, output. The largest rows decide the order below; do not guess.

**Where the waste is expected, by cause**
1. **Turns.** Each turn is a model call that re-sends the transcript. An agent that records one fact or one document per turn takes ten turns where two would do. Record many per turn; give small files to the reader whole, in the prompt, instead of having it list and open them.
2. **Output.** Output tokens cost most and take longest. Thinking set higher than a mechanical step needs; text the model writes that the product now derives itself (the first request letter comes from the item list); summaries nobody reads.
3. **Agents with nothing to do.** A documented process with all its needs settled needs no proposal loop; one check call can judge all quotes at once.
4. **Waiting in a row.** Steps that do not depend on each other run side by side (wall-clock only).
5. **Shared prefix.** Instructions, process and case text in the same order for every agent, so each reads them from the cache.

**The proof.** A change counts only if it holds under this protocol, run before and after:
- three cases never run on this deployment in this form (a small, a middle and a large cut, uploaded as new files so reading happens again), started cold (no warm cache);
- wall-clock from the click to "prepared", time to the first line on screen, calls, tokens (gross, non-cached, output);
- then the seven development cuts re-scored: no row worse on any case.
Report the before/after table with the cases' sizes. A gain that appears only on a warm cache or a re-run is not a gain.

## U · The handler's screen

**One screen answers three questions, in this order: What is this case? What needs me? What is CasePath doing?** Everything else is one click away and never in the way.

**Words.** No agent names, no tool names, no model words on any handler screen. The tabs are the handler's things, not our machinery: **Übersicht · Akte · Prozess · Unterlagen · Verlauf.** (What the five agent tabs show today moves under these; "Verlauf" holds the work log for those who want it.)

**A run is the Übersicht filling in, not a different view.**
- A line of five stages in handler words (Lesen · Prozess · Fakten · Unterlagen · Prüfung) with real elapsed time and the expected rest.
- One sentence says what is happening now and where ("liest die Schadenmeldung, S. 3"), and opens that page.
- Der Fall's lines appear as they are established, each with its source; the process shows the step reached; documents tick in; the letter assembles last.
- Braucht Ihr Urteil receives its points while the run goes on.
- Nothing moves unless the case's state changed.

**Steering while it runs.** A handler must be able to turn the work before it has gone the wrong way:
- **The process is shown first,** within the first half-minute, with "anderer Prozess" beside it. No answer means yes; choosing another restarts only what depends on it.
- **A point answered during the run is taken at once:** the handler's value stands, the agents do not ask again, and what depends on it follows.
- **Anhalten** stops the run and keeps what is established; **Weiter** continues from there.

**Steering, design for the team loop (not built yet):**
1. *Stop:* a per-run flag in the store, set by "Anhalten"; `run_agent` checks it before every model turn and `CaseTeam.run` before every delegation, then ends with status "paused", saving `work` (brief, facts, documents, verdicts, usage) as the run's result with `paused_at`.
2. *Continue:* "Weiter" starts a run from the paused one: `CaseWork` is rebuilt from that result, finished delegations are skipped by a `done` list in the plan, and only the open step and those after it run.
3. *A point answered during the run:* the handler's value is a `set_fact` edit; `work.facts` takes every edit at the start of each turn, `_record_fact` refuses to overwrite a fact set by hand, and the source checker skips it.
4. *Anderer Prozess:* choosing another workflow during or after the run keeps the reading (brief, page texts, located quotes) and repeats only what depends on the process: the fact pass for facts the new workflow adds, the finder, the checker and the result.
5. *Shown first:* routing emits `process.ready` within the first turn; the Übersicht shows the process with "anderer Prozess" beside it, and no answer means yes.

**As little as possible asked of the handler.** A point appears under Braucht Ihr Urteil only if a person's answer would change the path, the letter or a deadline. Everything else CasePath settles and shows as settled, with its source. A typical case: three points or fewer.

**Done when** a handler who has never seen CasePath opens a prepared case and, without a word of explanation, says what the case is, decides every point, changes one thing they disagree with, and closes it; and when, watching a run, they can say at any moment what is happening and stop or turn it.
