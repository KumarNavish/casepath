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


## Served-build result

Product source: `17a086ce2c3e4c02d164d397e8a6aadfcdfc8766`.
The [receipt](presentation-receipt.json) binds the served deployment, five served
assets and unchanged operation fixture. The source manifest is
`7359e21421e429826a3bf21d9cf9e0ee353fcddb60b34a4e014ea0aedd64401a`.
Adding this evidence changes no product or manifest-covered source.

- All 5,745 clock samples passed; `document.getAnimations()` stayed empty.
- All 13 rendered views passed clipping and unintended-overlap checks.
- Each act's live frame and capture frame matched byte for byte: mean pixel
  difference 0. Pause/Resume and exact-source inspection passed.
- All six reduced-motion checks reached the same instant state while preserving
  the timeline. Page, context and browser closed normally within the 10 s bounds.
- The full live run measured p50 16.7 ms, p95/p99 16.8 ms and maximum 16.8 ms
  between observed animation frames; no interval exceeded 34 ms. This is a
  measurement on this host, not a guarantee for every machine.
- [71 focused tests](w9-focused-final.tap), [353 workspace tests](w9-workspace-final.tap)
  and [35 browser regressions](w9-browser-regressions-final.tap) passed.
  [Source verification](w9-built-head.log) and [prepare](w9-prepare.log) passed.

The first fixture-only attempt lacked browser warm-read responses; those are now
recorded in the fixture. The first fixed-shell ending overlapped the transport;
its excess margins were removed and the geometry check now passes. An initial
seal command lacked its required source-commit environment; the prescribed
sealing sequence then verified. The first served-proof attempt ran before the
preview was listening and failed to fetch; the successful receipt above was run
after startup completed. Earlier diagnostic logs remain in the owned runtime.

| View | Clock time | Rendered proof |
| --- | ---: | --- |
| Actual customer message | 0.000 s | [Customer](customer-message.png) |
| Exact passage and extracted fact | 9.349 s | [Source and fact](fact-rest.png) |
| First node accepted | 34.999 s | [Accepted node](node-rest.png) |
| Completed process | 56.799 s | [Decision](completed.png) |
| Legal tests, answer and unsent draft | 72.649 s | [Answer](draft-rest.png) |
| Verified checklist reuse | 87.349 s | [Learning](memory-notice-rest.png) |
| Nine recorded cases | 95.749 s | [Cases](wordmark-rest.png) |

## W9b capture protocol

W9a was approved at `a9e8725` in planner comment 6325303636. Its followups are
applied here: the closing case shell crossfades to **Cases · Knowledge**, with
Cases active and no case-specific sources. The closing wordmark has at least
32 px of clear space above and below. Capture leaves the visible control on
**Pause** at every frame. **Watch this case** is hidden during playback, and
**Skip to answer** is hidden when the answer or case list is on screen.

The receipt's Next legitimate action already requires W9 approval before READY
FOR MAC. The presentation verifier also samples `document.getAnimations()` on
every observed frame of the full live run, in addition to every capture sample.

`capture_film.mjs` requires a committed recorder, clean product source and an
exact matching served deployment. It reads the sealed static build and frozen
recorded GET fixtures; it rejects writes, external requests and unrecorded API
reads. Chromium runs at 1440×900 with deviceScaleFactor 2, UTC and en-GB. The
receipt records the browser version, asset hashes and fixture hashes.

```sh
node design-plans/w9-20261021/capture_film.mjs \
  --out /durable/path/outside/the/repository
node design-plans/w9-20261021/capture_film.mjs \
  --verify /durable/path/outside/the/repository/film-receipt.json
```

Every raw PNG has a sequential index and the exact clock time `n × 1000/60`.
The frame index hashes every PNG, and the independent repeat compares every
60th frame. The only edits are half-second fades from/to white within the
existing duration. All outputs are H.264 High, yuv420p, CRF 16, 60 fps, with no
audio. The projector version fits the complete 16:10 picture inside 1920×1080
with 96 px white side bars; it does not crop or stretch it. The master and raw
frames stay outside Git. The 24-frame contact sheet is decoded from the final
16:10 MP4, including its permitted fades.

`--probe` checks 120 frames and all three encodes without creating deliverables
in the repository. The complete film and its receipts follow the sealed capture.
