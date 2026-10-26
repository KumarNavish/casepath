# Demo finish: guided film with plan, photo reading and knowledge library

The user asked for a finished, self-explanatory product film for executives
without legal or technical background. It shows CasePath working end to end:
it plans a case and builds its document checklist, checks documents with
proof, gives a suggested answer, reuses learned checklists, and reads a
customer photo. Every step is labelled in plain language, and the film shows
live work between short explanations. The film is a deterministic replay of
the product's own presentation mode (`?present=1#autonomous/demonstration`)
from frozen fixtures. It makes no writes and no model calls.

## What the film shows, and where each part comes from

| Chapter | On screen | Source |
| --- | --- | --- |
| 01 The request | Customer message; the request passage is marked | Recorded customer source and `deskRequest` span |
| 02 The plan | Reused checklist, three questions appear, then three required documents | `knowledge.reuse` (seq 123), `node.evaluate` (128, 131, 134), `document.require` (135–137) |
| 03 The checks | Each document is checked against its exact passage and the checklist ticks; the decisive passage becomes a fact; questions are answered | `document.check` (165, 194, 223), fact and `step.complete` operations (265, 306, 347) |
| 04 The answer | Five rule checks, one unmet; suggested answer, open points, unsent draft | Recorded legal predicates, outcome and request draft |
| 05 The next case | A later case of the same kind reuses three checks with its own facts | Recorded learning replay for `clm_7dbd7c7d1c4ddf90` |
| 06 Photos | A scan line lights 144 measured dark spots, outlines the area, and reads the capture date | `GET …/sources/{claim}/{artifact}/photo-reading` on the corpus photo |
| 07 Learning | The Knowledge page for three kinds of case, each learned once and reused | Recorded knowledge index (three procedures, version 1) |
| 08 CasePath | Closing card | Static copy |

## Photo reading (new, no model)

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

1. **Fidelity.** [Side-by-side images](proof/fidelity) were inspected for all three concepts.

   | Concept | Mean difference | Film frame |
   | --- | --- | --- |
   | 01 | 3.91% | 46.0 s, live document reading |
   | 02 | 4.03% | 87.0 s, rule checks |
   | 03 | 4.09% | 114.5 s, checklist reuse |

   Layout, palette, type, question spine, source pane and the source → checklist → result chain match. The deliberate differences are listed below, and no item is pending.
2. **Motion.** The film shows one change at a time, and the cursor arrives before the highlight. Live work runs between captions. Lead captions clear within 2.6 s, and hold captions frame a result. The recorded-trace browser test covers the following:
   - the clock;
   - plan rows;
   - exact source citations;
   - operation order;
   - one current spinner;
   - acceptance order;
   - backward-seek determinism.

   It also binds the plan, checklist and photo data to the recording, and audits geometry on every frame at 60 fps.
3. **Cold viewer.** A fresh reviewer received 24 evenly spaced frames with no context. Its brief was a nontechnical insurance executive watching a silent video, and its [verbatim response](proof/cold-viewer/response.md) is kept.

   It correctly described what the product does: a customer's documents lead to a checked answer that a person approves. It also described how results are reached: plan → document checks with exact sentences → rule checks → suggested answer and unsent draft → checklist reuse, photo marking and a learned library. It named the value as faster, consistent, traceable first assessments under human control.

   Its misses were fixed in the product and the film was recaptured:
   - The closing card was off centre.
   - A caption claimed the later case had "different documents"; it now says "their own documents".
   - A caption mentioned a tick that is not drawn.
   - The unmet-check caption covered the passing checks.
   - The library highlight cut through the column headings.
   - A double negative now reads "The later email is separate from the notice".
   - "All names are made up" sat beside a real insurer's name; it now reads "made-up customers and cases".
   - "A replay of real CasePath work on made-up cases" now reads "Recorded CasePath work. The cases are made up."

   The remaining points are recorded content or deliberate. They are listed under limits.
4. **Real function.** See *Verification* below. All 15 non-browser front-end suites pass (742 tests). The three browser suites pass, and the presentation browser test covers every film frame. The photo-reading and autonomous API tests pass. The full `./bin/casepath test` status is recorded there.

## Deliberate differences

- **Captions.** The north star asked for a film without captions. The user later asked for onboarding-style spotlights with short explanations between live work, and that instruction prevails. The captions explain only; every claim they make is bound to recorded context.
- **Transitions.** Scene changes are 0.7 s dips: the old view fades out fully before the new one fades in. They are not 0.5 s crossfades, because crossfades of dense pages read as clutter.
- **Speed label.** The condensed final question is labelled "Sped up" in plain language, not "4×".
- **Concept 02.** The completed-process overview, chain, law and source-check scenes were removed at the user's request ("show really magical work without wasting their time"). The answer view carries the rule checks.
- **Concept 03.** It shows "Before / Now · Edited by reviewer" and an expert-reviewed memory. The recordings contain no reviewer edit and no expert review, so the film claims neither. It says "A person still reviews the result."
- **Copy.** Role names, questions, fact labels and checklist rows use plain words, for example Reader, Fact checker, Planner, Document finder and Answer writer. Recorded document text is shown unchanged.

## Limits

- **Recorded text.** The customer email and rent form are in German. The lease text and the later email are dense legal English. The recorded outcome summary and the draft reply cite "CO 269d(2)(b)". Recorded content is not rewritten. A plain answer line is shown above it, and it is derived only from the recorded assessment and the failed predicate.
- **Later case.** The synthetic later case has a different tenant. Its four document types match the main case, and its landlord's email repeats the main case's wording.
- **Photo.** The photo case is not one of the nine recorded runs; only its photo reading is real. The reading is pixel measurement. It misses part of the darker upper mould area, names no cause and admits no evidence. On other corpus photos the detector also gave false hits (a window, wardrobe wood) and missed some mould.
- **Knowledge.** The learned checklists passed automated checks only. No expert review is claimed.
- **Things left unexplained.**
  - The role tabs change as different assistants work.
  - The question numbers beside the rule checks are not explained.
  - The header chrome differs between the case views and the Knowledge page.
  - The recorded order checks question 2's documents before question 1 is answered.
- **Hosted site.** The public site does not yet include the new endpoint, fixture or assets; that needs the Mac release.

## Film and source binding

See [film.json](proof/film.json): the capture source, asset SHA-256 values, duration, frame count, and the absence of writes, page errors and missing fixture reads.

## Verification

Pending: the final browser-suite run on these exact assets, sealing per `CONTRIBUTING.md`, and the full `./bin/casepath test`. This receipt is not yet a sealed acceptance.
