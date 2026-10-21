# W9a — the recorded demonstration

Stacked on approved W8 `58512a88b454fd57afbfe044d673d61cc27fa709`.
This change stays local and recorded: no inference, provider call, original-nine
run, hosted write, merge or deployment. The Mac owner retains integration.

The desktop Demonstration uses the product's existing source, process, legal-test,
draft, checklist and case-list views. `?present=1#autonomous/demonstration` starts
hands-free. Normal entry waits for **Watch the analysis** and then runs the same
story. Pause, source inspection and Skip to answer remain available. The first
message and its request are the exact saved customer source. Supporting passages,
facts, completed nodes and checklist reuse come from admitted operations.
The header and source rail stay in place through all six acts. The final case
list uses the same recorded rows inside that shell.

Both complete recordings pass the existing source, journal, checkpoint and final
state checks before the presentation clock starts. The clock creates no CSS or
Web Animations. Live playback and capture sample the same timeline and transform /
opacity interpolation. The 4× section keeps every meaningful reading hold at
900 ms; motion is `max(normal duration / 4, 250 ms)`. The badge stays visible
through the holds. Reduced motion uses the same acts and holds with instant states.

## Recorded boundaries

- The first case has five supported legal tests. A failed test is not invented.
  The nine-case ending includes actual failed-test labels for the other cases.
- Its decisive node has Source facts, Law and Current evidence. No missing-evidence
  or reference-case column is invented for an empty record.
- The intake node has no node-bound extracted fact. Its actual cited completion
  is shown; the tenancy node combines its actual source-bound facts.
- “Later case” means the next recorded case in the demonstration roster. The UI
  asserts only its verified checklist reuse, with **Facts come from this case
  only** and **Qualified review is still required**. There is no unsupported
  Before/Now or expert-review claim.
- Source highlights intentionally overlay their cited text. The outgoing layer
  of a 400 ms crossfade intentionally overlays its corresponding canvas. The
  geometry audit excludes these two named decorative layers and checks every
  other visible box and control; neither exclusion changes product rendering.

## Verification

The presentation lasts **95.75 seconds**, or **5,745 samples at 60 fps**.
Act changes include their 400 ms crossfade; meaningful reading holds remain
at least 900 ms in the 4× section.

| Act | Start | Duration |
| --- | ---: | ---: |
| Customer | 0.00 s | 10.35 s |
| Reading | 10.35 s | 30.05 s |
| Process at 4× | 40.40 s | 15.60 s |
| Decision | 56.00 s | 16.65 s |
| Learning | 72.65 s | 14.70 s |
| Cases | 87.35 s | 8.40 s |

`verify_presentation.mjs` uses the served build and the unchanged, recorded
`desk-v3.json.gz` operation fixture. It rejects non-GET/HEAD requests, checks every
1/60-second timeline sample, captures every act and meaningful resting state,
checks clipping and unintended overlap, exercises Pause/Resume and exact-source
inspection, compares live paused frames with capture at the same clock times,
runs the full live presentation, and checks instant reduced-motion states.
Browser, context and page cleanup each have a 10-second bound.

```sh
CASEPATH_PROOF_OUTPUT="$PWD/.runtime/w9-proof" \
  node design-plans/w9-20261021/verify_presentation.mjs
```

The standalone clock and fixture-only browser tests are included in the strict
frontend suite registry. `casepath-qa/fixtures/presentation-v1.json.gz` contains
30 successful JSON GET responses captured from the owned deterministic local
preview on 2026-10-21. It includes the catalog, verified replay prefixes, knowledge,
source text and snapshots needed by the browser's warm reads. The operation
fixture remains unchanged. No response headers or credentials are stored.
The fixture SHA-256 is
`374b583fd0341a4701274e11f77d474ff92f3c15f2bd59383da7c666c0e57a80`.

W9b will produce the continuous film after W9a approval. The final full strict
gate and READY FOR MAC follow W9 approval on a sealed W8+W9 source.
