# Workspace UI: north-star self-review

The internal workspace (`casepath/web/ui/`) follows the three north-star concepts in `design/northstar/`. Everything on screen comes from the live API: the case store, the agents' recorded events and results, the case process and the Knowledge base. Nothing is replayed or staged.

## Fidelity

| Concept | Implemented | Deliberate differences |
| --- | --- | --- |
| **Shell** | Matched:<br>• 75 px top bar with the wordmark and the five agent tabs; the active tab is crimson with an underline<br>• 262 px sources rail with media icons, received dates and an active-row bar<br>• Mulish font and the north-star colour tokens | • A working agent's tab pulses while a run is live<br>• Rail rows add "Proof for questions …" from accepted findings<br>• Image sources show their thumbnail |
| **01: live decision building** | Matched:<br>• spine with done, building and waiting rings<br>• source card with e-mail header fields and the body in its own lines<br>• the crimson pointer and the working agent's hexagon, landing at the end of the quote being worked on; the quote is highlighted only after the pointer arrives<br>• "Building “…”" plan with the agent's latest steps<br>• fact cards (source + finding) with the dotted connector up to the source | • While a run is live, the spine is the case's process forming from the agents' `process.state` events: each step is shown by the question that decides it (or its title); steps passed on a recorded but unchecked fact are crimson dashed ("located, being checked") and get their check when the source checker confirms them; branches the case did not take fall away under the step (struck through); the open question shows its branches. Paths longer than five steps show "+N earlier steps".<br>• A **Documents** card under the plan: the checklist grows from the process, each need under the step that needs it ("für «…»"), with found / missing / not yet looked for, and "Wissen vN genutzt" on needs that came from Knowledge<br>• The plan rows are the agent's real tool steps, not authored labels<br>• The pointer moves only to the target of the latest real operation: the quote, the document row, the step a fact decides, the file being read, otherwise the active plan row |
| **02: completed process** | Matched:<br>• numbered step nodes from the case's evaluation path: done (crimson, check), current (ring), waiting (dashed)<br>• branch boxes with the taken branch<br>• **Edit decision** on the selected node<br>• five-column evidence strip with "Documents N missing"<br>• timeline preview with the cited line on yellow | • Nodes are the process steps from the workflow catalogue, so labels are step names, not authored questions<br>• "Basis" replaces "Law"; it lists the workflow's sources |
| **03: edit and memory payoff** | Matched:<br>• BEFORE → NOW with "Edited by &lt;user&gt;"<br>• the documents the edit added, removed or changed, each with its checked status<br>• "Retrieved N Knowledge item(s)", with the earlier case's quote → the Knowledge item (the version this case used, "now vN" when it has moved on, use statistics) → the result in this case<br>• notice bar, shown only when Knowledge was applied<br>• Knowledge versions throughout: "v1 genutzt" in the evidence strip, "v1 genutzt → v2 vorgeschlagen · wartet auf Freigabe" for a proposed refinement, "verfeinert v1 → v2" on the Knowledge page | • The notice reads "Qualified review is still required" without claiming expert review, which is not recorded<br>• "Edited by" uses the signed-in user |

## Motion

While a run is live, the page polls the run's events every 1.2 s. It follows the working agent's tab without a navigation, so polling continues.
- **One change at a time.** A step, a fallen-away branch or a document need enters once, with a short fade, the first time it appears; later polls leave it still.
- **The pointer arrives before the highlight.** The pointer moves (0.5 s) to the latest operation's target; a new quote is tinted only once the pointer has reached it.
- **Recorded only.** Every node, branch, document row and version label comes from `process.state` events, which the agents emit after each finding, verdict and process change. These events carry ids and states, never quotes (`tests/test_team.py::test_the_process_forms_live_from_the_findings`).
- After a process edit, the re-check run is followed the same way, and the page then shows BEFORE → NOW.
- Reduced motion turns off the spinner, the pulse, the fades and the pointer's travel; a quote is highlighted at once.

## Fidelity measurement

`design-plans/tools/fidelity.mjs` on the synthetic preview at 1440×900:
- 01 against a live frame (the pointer at the quote): mean difference **5.04 %**;
- 02 against the completed process: mean difference **5.75 %**.

The differences are the deliberate ones listed above, plus recorded content in place of the concepts' illustrative text. No item is pending.

## Real function

A headless Chromium pass at 1440×900 on the synthetic preview (`deploy/preview/preview.py`) covered:
- the cases list;
- case A on every tab;
- case B before, during and after a live team run;
- the edit form, the live re-check, BEFORE → NOW, and the Knowledge page.

It showed zero console or page errors. The live run was captured every 1.8 s (10 frames): the process forms, the "not told" branch falls away, the four document needs appear under their steps and fill in, and the result shows the Knowledge refinement as "v1 genutzt → v2 vorgeschlagen". The preview data is synthetic and the model is scripted. A real-model pass needs the internal runtime.

## Cold viewer

Fourteen frames of the preview, in order (the live run of case B, the completed process, checklist and result, and the Knowledge page), went to a fresh reviewer with no context. The reviewer was asked to answer as "a nontechnical insurance executive watching a silent product video". In summary:

- **What it does:** prepares a tenant's mould claim for a legal-protection handler. It gives a short assessment, the documents still missing, next steps, and a reply draft that stays unsent until a person decides.
- **How:** named helpers take turns. The process builder lays out a three-step path, the source checker highlights the exact sentences as proof, and the document finder ticks off which documents exist. The result names its sources sentence by sentence. Knowledge keeps what earlier cases taught, and a suggested improvement waits for a person's approval.
- **Why valuable:** a faster and more consistent first review, every conclusion traceable to its sentence, missing paperwork flagged early, and learning that a person approves.
- **Unclear, and what changed:**
  - the live missing count (0, 1, 2) differed from the result: fixed. Once the document finder has looked, a need it did not find shows as missing live too;
  - agent summaries in English inside the German interface: fixed, they are now rendered in the interface language;
  - the preview's second case was titled for another address: fixed in the preview;
  - the scripted preview records no photo finding, so "Photo of the defect" shows as missing although a photo is attached. That is what the scripted run recorded, and is kept;
  - the synthetic workflow is in English, and the reviewer could not tell what is AI and what is fixed rules. Both remain open; the pilot's own processes are in German.

The reviewer did not use the words "the graph forms from the sources". They did describe a path built step by step, sentences highlighted as proof, documents ticked off against it, and Knowledge reused only after approval.

## Real model pass

Synthetic case B02 was run in the Databricks pilot on the workspace's Opus model: 23 calls, 4 min 40 s, 154k of 248k input
tokens read from the prompt cache.
- **Seen during the run:**
  - the pointer and hexagon moved to the quote being read;
  - quotes were highlighted;
  - the Documents card grew under its steps;
  - the plan and work log were in German, with no internal ids.
- **Found and fixed afterwards:**
  - the view followed the working agent even after the person chose a tab;
  - a tool name ("add_question") appeared in the work log;
  - the summary named missing documents the checklist did not;
  - "Routing: selected." was in English;
  - on a short window, the Prepare button was reachable only by scrolling the page.
- **The internal OSM+ processes,** with their 27 to 30 steps and long titles, were also checked in a local preview with a scripted run of benchmark case B01:
  - steps show a short title without the role prefix (the full title on hover);
  - wrapped rows have no stray arrows;
  - the evidence strip shows at most six facts.

## Pending

- The process spine during a real run, in frame. The B02 screenshots were scrolled below it.
- Mobile layout. Desktop at 1440 is the target, as in the north star.
