# Demo finish: guided film with plan, photo reading and knowledge

The user asked for a finished, self-explanatory product film for executives
without legal or technical background. It shows CasePath working end to end:
it takes a learned checklist off its shelf and turns it into the case's
questions and documents, checks documents with proof, gives a suggested
answer, reads a customer photo, reuses the same checklist for a new case, and
ends on everything it has learned. Every step is labelled in plain language,
and the film shows live work between short explanations. The film is a
deterministic replay of the product's own presentation mode
(`?present=1#autonomous/demonstration`) from frozen fixtures. It makes no
writes and no model calls.

After the first finished cut, the user asked for four things:

1. the five-tab concept header in every frame;
2. a memorable knowledge base;
3. a cinematic plan and new-case reuse;
4. a simple, clear edit.

This receipt covers the cut that answers those requests.

## What the film shows, and where each part comes from

| Chapter | On screen | Source |
| --- | --- | --- |
| 01 The request | Customer message; the request passage is marked | Recorded customer source and `deskRequest` span |
| 02 The plan | A shelf of the three learned checklists; the rent-increase card lifts off the shelf; its questions fly onto the case as circles, then its documents drop into the checklist | Knowledge index (three procedures, version 1); `knowledge.reuse` (seq 123), `node.evaluate` (128, 131, 134), `document.require` (135–137) |
| 03 The checks | Each document is checked against its exact passage and the checklist ticks; the decisive passage becomes a fact; questions are answered | `document.check` (165, 194, 223), fact and `step.complete` operations (265, 306, 347) |
| 04 The answer | Five rule checks, one unmet; suggested answer, open points, unsent draft | Recorded legal predicates, outcome and request draft |
| 05 Photos | A scan line lights 144 measured dark spots, outlines the area, and reads the capture date | `GET …/sources/{claim}/{artifact}/photo-reading` on the corpus photo |
| 06 The next case | A different tenant's case: the same shelf, the same card, the same gesture, bound to that case's own recorded operations | `knowledge.reuse`, `node.evaluate` and `document.require` of `clm_7dbd7c7d1c4ddf90` |
| 07 Knowledge | A map that replays the recorded history: each checklist is learned from its first case, then every recorded use lands as a ring on the case that used it. The counters reach 3 checklists, 9 cases and 15 uses | `learning_replay` of the knowledge fixture: 3 `knowledge.published`, 15 `knowledge.used` |
| 08 CasePath | Closing card | Static copy |

## Changes for the four requests

- **Header.** The film header is the concept bar in every scene: the brand,
  then *Claim reader · Source checker · Process builder · Document finder ·
  Result checker* with 1.5 px line icons. The active tab is crimson with an
  underline. Claim reader is active while the request is read. Process builder
  is active for the plan, the reuse and the knowledge map. During checks, the
  active tab follows the recorded role. Title cards show no active tab.
- **Knowledge.** The checklist shelf is the recurring device. Chapter 02 picks
  a card from it, chapter 06 picks the same card for a new case, and chapter
  07 shows where every card came from and where it was used. Every number on
  the map is counted from the recorded events.
- **Plan and reuse.** The plan is one continuous gesture:
  1. shelf;
  2. lift;
  3. the card flies to the case;
  4. question slips fly onto the case's questions;
  5. documents drop in.

  The later case replays the same gesture from its own recorded operations,
  so the viewer sees the reuse without a separate explanation scene.
- **Edit.** The memory view and the static library page were removed. Photos
  now come before the next case, so the film ends on what was learned.
  Captions are one short headline and one detail line.

## Photo reading (no model)

`casepath-api/casepath_api/photo_reading_v1.py` is a deterministic Pillow
measurement. It reads the EXIF capture date. On light, low-colour surfaces it
finds small dark marks against the locally smoothed surface, and it finds
light brown staining. It returns at most three areas, with their position,
share and the measured marks in original pixels. It names no cause, material
or legal consequence.

The read-only endpoint binds the reading to the original's SHA-256. It
returns 415 for non-images, and it always reports `evidence_admitted: false`.
`casepath-api/tests/test_photo_reading_v1.py` covers the following:

- synthetic spotting and staining;
- a clean wall;
- determinism;
- EXIF presence and absence;
- corrupt bytes;
- the API, against the real corpus photo, with no store writes.

The film's photo, `clm_731b214dde882f89 / src_8291405543acf1003fa5b7c1824e8551`,
comes from a frozen fixture, `casepath-qa/fixtures/photo-reading-v1.json.gz`,
that the real endpoint generated.

## North-star self-review

1. **Fidelity.** [Side-by-side images](proof/fidelity) of the final cut were
   inspected for all three concepts. Mean difference is the mean absolute
   RGB difference with the frame resized to the concept, as recorded in
   [film.json](proof/film.json).

   | Concept | Mean difference | Film frame |
   | --- | --- | --- |
   | 01 | 3.90% | 48.85 s, live document reading |
   | 02 | 3.94% | 89.85 s, rule checks |
   | 03 | 3.53% | 130.6 s, the new case's checklist after reuse |

   Layout, palette, type, question spine, source pane and the source →
   checklist → result chain match. The header now matches the concept tab bar.
   The deliberate differences are listed below, and no item is pending.
2. **Motion.** The film shows one change at a time, and the cursor arrives
   before the highlight. Live work runs between captions. Lead captions clear
   within 2.6 s, and hold captions frame a result. The recorded-trace browser
   test covers the following:
   - the clock;
   - plan rows and question circles, bound to the case's recorded operations
     after reuse;
   - shelf cards and the selected checklist for both cases;
   - knowledge-map counters, rings and lit cases against the recorded replay;
   - exact source citations;
   - operation order;
   - one current spinner;
   - acceptance order;
   - backward-seek determinism.

   It also audits geometry on every frame at 60 fps.
3. **Cold viewer.** A fresh reviewer received 24 evenly spaced frames of the
   cut before the final fixes, with no context. Its brief was a nontechnical
   insurance executive watching a silent video. Its
   [verbatim response](proof/cold-viewer/response.md) is kept.

   It described the whole flow correctly:
   1. the checklist taken from the shelf;
   2. three questions;
   3. highlighted proof sentences;
   4. five checks with one failure;
   5. the suggested answer;
   6. the unsent draft;
   7. the photo reading;
   8. the reuse for a new case;
   9. 3 checklists, 9 cases and 15 uses.

   It would remember that "every answer points to the exact highlighted
   sentence … and a person always makes the final decision", with "a checklist
   that is learned once and reused on later cases" a close second.

   Fixed in the product and recaptured:
   - Claim reader was not active while the request was read.
   - The counters read "1 cases".
   - The rings touched the case names.
   - A wire's moving dot ran ahead of its line.
   - The first-case wires crossed their labels.
   - The ring caption now says "Each ring is one recorded use."

   Its other points are recorded content or deliberate, and are listed under
   *Limits*. It also flagged that the email is addressed to Protekta. Protekta
   is the client's own brand, so the address is kept. The footer says the
   customers and cases are made up.
4. **Real function.** See *Verification*.

## Deliberate differences

- **Captions.** The north star asked for a film without captions. The user
  later asked for onboarding-style spotlights with short explanations between
  live work, and that instruction prevails. The captions explain only. Every
  claim they make is bound to recorded context.
- **Transitions.** Scene changes are 0.7 s dips. The old view fades out fully
  before the new one fades in. They are not 0.5 s crossfades, because
  crossfades of dense pages read as clutter.
- **Speed label.** The condensed final question is labelled "Sped up" in plain
  language, not "4×".
- **Concept 02.** The completed-process overview, chain, law and source-check
  scenes were removed at the user's request ("show really magical work without
  wasting their time"). The answer view carries the rule checks.
- **Concept 03.** It shows "Before / Now · Edited by reviewer" and an
  expert-reviewed memory. The recordings contain no reviewer edit and no
  expert review, so the film claims neither. The knowledge map shows only
  recorded learning and use.
- **Copy.** Role names, questions, fact labels and checklist rows use plain
  words. Recorded document text is shown unchanged.

## Limits

- **Recorded text.** Recorded content is not rewritten:
  - The customer email and rent form are in German.
  - The lease text and the later email are dense legal English.
  - The recorded outcome summary and the draft reply cite "CO 269d(2)(b)".

  A plain answer line is shown above them, derived only from the recorded
  assessment and the failed predicate.
- **Recorded order.** The recording checks question 2's documents before
  question 1 is answered. It ties the lease to question 2. The active tab
  follows the recorded role, so it moves between assistants during the checks.
- **Later case.** The synthetic later case has a different tenant. Its
  document types match the main case, and its landlord's email repeats the
  main case's wording. The film shows its reuse, not its answer.
- **Uses.** A "use" is one recorded `knowledge.used` event. Each reused three
  document rules. The film claims no time saved, accuracy or cost, because
  none was measured.
- **Photo.** The photo case is not one of the nine recorded runs; only its
  photo reading is real. The reading is pixel measurement. It misses part of
  the darker upper mould area, names no cause and admits no evidence. On other
  corpus photos the detector also gave false hits (a window, wardrobe wood)
  and missed some mould.
- **Knowledge.** The learned checklists passed automated checks only. No
  expert review is claimed.
- **Things left unexplained.** The question numbers beside the rule checks are
  not explained.
- **Hosted site.** The public site does not yet include the new endpoint,
  fixture or assets; that needs the Mac release.

## Film and source binding

See [film.json](proof/film.json). It records:

- the capture source;
- the asset SHA-256 values;
- the duration and frame count;
- that there were no writes, page errors or missing fixture reads.

## Verification

On the sealed assets of `ea57a2fa`:

- **Film capture.** 4,896 frames, 163.2 s, with no writes, page errors or
  missing fixture reads. The asset hashes in [film.json](proof/film.json)
  equal the committed assets.
- **Front-end suites.** All 33 non-browser suites pass (939 tests). The
  presentation browser test passes. It checks every film frame, the plan and
  map bindings, and backward-seek determinism.
- **Sealing.** The `CONTRIBUTING.md` sealing commands ran, and the release
  manifest verifies.
- **Pending.** The review and unified-product browser suites, and the full
  `./bin/casepath test` in a fresh clone, are still running. The full suite
  refuses to run in a Git worktree.
