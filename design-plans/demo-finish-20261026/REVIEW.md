# Demo finish: a clear, case-by-case product film

The user asked for a finished, self-explanatory product film for executives
seeing CasePath for the first time. The film is a deterministic replay of the
product's own presentation mode (`?present=1#autonomous/demonstration`) from
frozen fixtures. It makes no writes and no model calls.

The latest request was to make the film clear, intuitive and memorable. It
named four refinements:

1. clear case storytelling;
2. crisp guiding narration;
3. a memorable email draft;
4. intuitive attachments.

The test it set: at any moment, an executive understands which case, what
problem, what action, why it matters, and what CasePath learned.

## The film, case by case

| Time | On screen | Source |
| --- | --- | --- |
| Title | "From a customer's documents to a clear answer" | Static copy |
| Case 1 opener | A big "1", Elin Ziegler, the problem in one line, the four documents with their file icons, and a docket of the three cases. The card then settles into the case block at the top of the file list. | Name from the recorded customer message header. Problem restates the recorded subject. Documents from the recorded source descriptors. |
| Case 1 · request | The customer message, with the request marked | Recorded customer source and request span |
| Case 1 · plan | The shelf of three learned checklists; the rent-increase card comes off it; its 3 questions and 3 documents land on the case | Knowledge index; `knowledge.reuse` (seq 123), `node.evaluate` (128, 131, 134), `document.require` (135–137) |
| Case 1 · checks | Each document is checked against its exact sentence. The file then shows "Proof for question N" and the checklist ticks. | `document.check` (165, 194, 223), facts and `step.complete` (265, 306, 347) |
| Case 1 · answer | Five rule checks, one unmet; "The rent increase is not valid: no reasons were given with it." | Recorded legal predicates and assessment |
| Case 1 · reply | Left, "What it found": three findings, each with the file that proves it. Right, the reply draft: each recorded clause appears as its finding links to it. The draft ends sealed "Draft · not sent — you decide". | Recorded `request_draft` (`prepared_not_sent`), the failed and later-email predicates and their citations, and the recorded open points |
| Case 2 opener · photo | "Case 2 · First look · Only the photo is read". The photo opens out of its own thumbnail in the file list. A scan lights 144 measured dark spots, outlines the area and reads the capture date. | `GET …/photo-reading` on the corpus photo, frozen in `photo-reading-v1` |
| Case 3 opener · reuse · answer | Drew Shaw, "Same kind as case 1". The same shelf, card and gesture, bound to this case's own operations, then its own recorded answer. | `knowledge.reuse`, `node.evaluate`, `document.require` and the outcome of `clm_7dbd7c7d1c4ddf90` |
| Knowledge | A map that replays the recorded history: 3 checklists, 9 cases and 15 uses, with cases 1 and 3 named where their rings land | `learning_replay`: 3 `knowledge.published`, 15 `knowledge.used` |
| Finale | "Every answer shows its proof. A person decides. … Nothing in this recording was sent." | Static copy |

## How the four refinements were met

- **Case storytelling.**
  - Each case opens on its own card: case number, customer, problem and documents.
  - The card docks into a case block that stays at the top of the file list. The block shows the number, kind, customer, problem and, once reused, the learned checklist.
  - A docket shows where the case sits among the three.
  - Narration names the case: "Case 1 · Elin Ziegler".
  - Case 3 is "Same kind as case 1", with its own problem line and its own answer.
- **Narration.**
  - Each card is dark, with a crimson edge, so it cannot be mistaken for the white product.
  - It has two lines: what is happening, then why it matters, after an arrow.
  - Cards dock bottom right, with a leader line to the spotlight.
  - Narration stays on screen through every scene.
  - The first time each assistant's tab lights, a tooltip says what that assistant does.
- **Email.** The checked findings, each with its proof file, link one by one into the recorded clauses of the draft. "In short" carries the plain answer beside the draft, not inside it. The draft ends sealed as not sent. No letter text, greeting or send control is added.
- **Attachments.**
  - Each file has a recognisable icon: a PDF tag, a Word tag (supported; no Word file is in the recordings), an envelope for email, and a text page.
  - A photo shows its own thumbnail with a preview badge, and the photo opens out of it.
  - Each file used as proof shows "Proof for question N". Questions answered by its passage are included, and the line appears only once its check is shown.

## North-star self-review

1. **Fidelity.** [Side-by-side images](proof/fidelity) of the final cut were inspected for all three concepts. The mean difference is the mean absolute RGB difference, with the frame resized to the concept (see [film.json](proof/film.json)).

| Concept | Product layer | As filmed (with narration dim) | Film frame |
   | --- | --- | --- | --- |
   | 01 | 4.78% | 24.58% | 43.45 s |
   | 02 | 4.06% | 20.71% | 93.45 s |
   | 03 | 3.81% | 18.99% | 148.2 s |

   Layout, palette, type, question spine, source pane, the source → checklist → result chain and the concept header match. The deliberate differences are listed below.
2. **Motion.** The film shows one change at a time, and the cursor arrives before the highlight. Live work runs under narration that always names the case. The recorded-trace browser test covers:
   - the clock;
   - plan rows and question circles bound to each case's recorded operations;
   - shelf cards;
   - knowledge-map counts;
   - the reply: a byte-exact recorded body, three linked clauses, an unsent boundary and no send control;
   - exact citations;
   - operation order;
   - backward-seek determinism;
   - geometry on every frame.
3. **Review panel.** Four independent reviewers saw the cut before the final fixes. Their outputs are kept in [proof/reviews](proof/reviews), with the cold viewer's [verbatim response](proof/cold-viewer/response.md).
   - **Cold executive.** Understood three cases, the proof-first answers, the unsent reply and the reuse. It would remember "Every answer shows its proof. A person always decides."
   - **Ultimate-test audit** (30 frames, every 6 s).

     | Question | Pass rate |
     | --- | --- |
     | Which case | 100% |
     | What problem | 100% |
     | What action | 83% |
     | Why it matters | 53% |
     | What was learned | 74% |

     Most failures were frames without narration.
   - **Honesty.** No invented numbers, names or amounts. It flagged result cards shown before their beat, overclaiming captions, the photo case staged as fully handled, and incomplete proof badges.
   - **Visual editor.** The openers, case block, narration cards and reply links work. It flagged:
     - full white dips between steps inside a case;
     - leader lines crossing text;
     - case 3's checklist showing through its opener;
     - the dim snapping off at scene changes;
     - a 13 s narration gap.

   Fixed before the final cut:
   - narration stays on screen through every scene;
   - fact cards appear only at their own beat;
   - "Proof" marks and checklist ticks change in the same frame;
   - the file being checked shows a magnifier, not a tick;
   - a passage that answers a question marks its file as proof for that question too;
   - Case 2 is "First look · Only the photo is read" and its caption names no cause;
   - Case 3 has its own problem line and ends on its own recorded answer;
   - "Reused: Rent increases" stays in the case block;
   - no active tab on openers or the map;
   - map labels name the film's cases;
   - the captions "every time", "always", "traces back to proof" and "Nothing is sent automatically" became scoped wording;
   - the finale says "Nothing in this recording was sent";
   - the reply header says "Draft reply · assessment text";
   - inside a case, the file list stays put and only the work area dips; full fades are kept for case changes;
   - leader lines were removed;
   - case 3's checklist stays hidden under its opener;
   - the dim and outgoing caption ease out over a scene change;
   - proof lines list every question a file answers ("questions 1, 2 and 3").
4. **Real function.** See *Verification*.

## Deliberate differences

- **Captions.** The north star asked for a film without captions. The user later asked for onboarding-style guidance, and that instruction prevails. Every claim in a caption is bound to recorded context.
- **Transitions.** Scene changes are 0.7 s dips; a case opener docks into its case block instead of dipping.
- **Concept 02.** The completed-process overview, chain, law and source-check scenes stay out at the user's request; the answer view carries the rule checks.
- **Concept 03.** It shows "Edited by reviewer" and an expert-reviewed memory. The recordings contain neither, so the film claims neither.

## Limits

- **Recorded text.** The customer email and form are in German. The lease and later email are dense legal English. The draft body is a legal assessment citing "CO 269d(2)(b)", not a customer letter. Recorded text is not rewritten. Plain lines ("In short", the answer line) are derived only from the recorded assessment and failed check.
- **Recorded order.** Question 2's documents are checked before question 1 is answered. In the answering pass, the right-hand step list shows that node's steps afresh. The active tab follows the recorded role.
- **Case 2.** Not one of the nine recorded runs. Only its photo reading is real: pixel measurement, no cause, no evidence admitted. No customer name is recorded for it.
- **Case 3.** Its document types match case 1, and its landlord email repeats case 1's wording.
- **Uses.** A "use" is one recorded `knowledge.used` event. No time saved, accuracy or cost is claimed.
- **Knowledge.** Automated checks only; no expert review is claimed.
- **Hosted site.** The public site does not yet include the new endpoint, fixture or assets.

## Film and source binding

See [film.json](proof/film.json): the capture source, asset SHA-256 values, duration, frame count, and the absence of writes, page errors and missing fixture reads.

## Verification

On the final assets (film and asset hashes in [film.json](proof/film.json)):

- **Film capture.** 5,523 frames, 184.1 s, with no writes, page errors or missing fixture reads.
- **Front-end.**
  - All 33 non-browser suites pass (939 tests).
  - The presentation browser test passes (6/6). It checks every film frame, the case openers, the reply bindings and backward-seek determinism.
  - The review north-star browser test passes.
- **API.** The photo-reading and autonomous API tests pass (8).
- **Sealing.** The `CONTRIBUTING.md` sealing commands ran after the final commit of these assets.
- **Full suite.** `./bin/casepath test` refuses to run in a Git worktree, so it ran in a fresh clone of the final commit `a194236c`: 2,901 passed, 13 skipped and 29 failed, in 70 min. All 29 failures come from the container, not the code:
  - 27 local-data-root tests fail closed by design. The audit cannot read the memory map of the container's own init process (PID 1, the Firecracker `process_api`), which shares the tests' user. On macOS the audit uses `lsof` instead.
  - The 2 browser suites failed because the clone sat under a long scratch path. The runner's temporary directory was 112 characters, and Chromium's socket paths exceed the 108-character Unix limit, so it crashes with SIGTRAP; a 47-character path launches. Both suites then pass through the runner's own `test_frontend_node_suites_v1.py`, with its clean environment, from this short-path checkout: 2 passed in 4 min.
- **Unified-product browser suite.** It is not part of the release gate. It also fails in this container at `0dccfd6b`, the commit that last edited it, with a full environment, on a viewport-fit check. It predates this work. An earlier note citing `07935305` used a checkout without a Python environment and has been corrected.
