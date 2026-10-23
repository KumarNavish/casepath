# W11: final UI handoff

W11 follows the user's final item: fit every live checklist row, show a spinner only for the operation playing, recapture and complete the north-star checklist. It supersedes `60d4907ca5c975e288fa3c0973992abd31fcc594`. After the verified PR21 handoff, no further UI changes are permitted except defects the Mac owner reports on PR21. Release remains with the Mac owner.

## Change and evidence

The live checklist grows naturally. If the card cannot fit above the film controls and Work log, completed rows collapse into exactly `✓ <n> done`; unfinished rows remain visible. A compact row spacing accommodates dense unfinished groups. A group is active only while its recorded current operation is playing. Completed groups and groups awaiting later operations do not spin. No plan row or operation is invented.

The every-frame audit also found clipped entrance motion, a tight Checked line height, fixed-height completed questions and line-clamped chain labels. Their containers now fit their content. Visual review also found a partially scrolled source heading; passage positioning now keeps the filename heading intact, and the frame audit covers it. At a process-completion film beat, the single source-matched fact remains visible; earlier recorded facts stay in the inspectable history. This preserves the same fact/source operation used before W11.

Focused verification passed 81 tests. The final browser rerun passed both tests after extending label coverage. All 5,283 deterministic film frames passed: 3,800 checklist-row checks, 601 fact-card checks and 177,726 label checks across all six acts; 207 frames exercise the completed-row summary. The test deliberately crops a checklist, legal-test label, case title and source heading and requires the audit to reject each crop.

The audit checks original rectangles, text fragments, viewport and clipping ancestors, plus independent content overlaps. It excludes intentional crossfade/connector/cursor layers and full source-document bodies. Scrolled-away answer labels are not visible content; partial clipping remains a failure. Original checklist and fact checks never use that exemption. The existing broad overlap audit remains in addition.

## North-star self-review

1. **Fidelity:** all three [pairs and overlays](proof/fidelity/fidelity.json) were inspected. Mean differences: 01: 4.73%, 02: 6.15%, 03: 5.02%. The receipt lists matched and deliberate differences; no pending deviation remains. The exact recorded showcase and question/fact glossaries remain those documented in [W10](../w10-20261022/REVIEW.md).
2. **Motion and source:** the capture and repeat audit every frame. Recorded-trace tests preserve plan rows, exact source citations, operation order and one current spinner. The presentation verifier checks one change at a time, cursor-before-highlight, pause, visible 4× acceleration and all six acts. The final walk must also pass reduced motion.
3. **Cold viewer:** a fresh reviewer received only 24 evenly spaced decoded frames, without task history, as a nontechnical insurance executive watching a silent product video. The [exact response](proof/cold-viewer-response.md) and [assessment](proof/cold-viewer.json) are retained. It recognized the product, source-to-result reasoning, value and reuse of checklist items with fresh later-case facts. Its limitations are retained below.
4. **Real function:** acceptance requires the original [final verification](final-gate/verification.json): one sealed commit, full strict `./bin/casepath test`, all eleven frontend suites, the unchanged protected Mac-owned test, and one complete serial seven-script walk through all nine cases. Missing or failed receipts are not a pass. The final evidence commit is separate from the tested source commit.

## Film and source binding

Capture source: `f777df0e05895207668540dcb5c01bddd6f4b544`. The film is 88.05 seconds at 60 fps: 5,283 frames with no dropped or duplicate indices. The independent repeat replays every frame and matches all 89 dense checksums. All six live comparisons are byte-identical; complete live playback passes with no console errors, writes or native animations. Capture/repeat geometry is saved in the original receipts and frame index.

- [1920×1200 film](proof/film/casepath-executive-1920x1200.mp4)
- [1920×1080 film](proof/film/casepath-executive-1920x1080.mp4)
- [Contact sheet](proof/film/contact-sheet.png) and [24 decoded frames](proof/film/contact)
- [Capture, repeat and live receipts](proof/film)
- [Served preflight](proof/served), [proof manifest](proof/manifest.json) and [retained diagnostics](proof/diagnostics)
- [Final gate and walk](final-gate/verification.json)
- [Canonical UI receipt](../../docs/product/UI_FINISH_RECEIPT_20261021.md)

The final source may add only this evidence/documentation and its source seal. Application, API, QA, fixtures, capture tools and served film assets must remain byte-identical to the accepted capture. The final source binding records the capture and tested identities, changed paths, manifest digest and asset hashes.

## Deliberate differences and limits

W11 deliberately lets the checklist and completed questions grow beyond illustrative fixed card sizes, collapses only finished work when required, and removes clipped chain-label truncation. W10's neutral question completion, honest legal-test failure labels, exact recorded passages, visible replay controls and unsent assessment remain. The histories contain no recorded alternative branch or human-reviewed memory change; none is fabricated. Qualified human review remains required. The film demonstrates recorded fictional cases, not measured accuracy, time savings or live handling performance.

Cold-viewer limits:

- The reviewer saw 24 evenly spaced decoded frames, not continuous motion; complete live playback and every-frame checks are separate receipts.
- The reviewer found dense bilingual source text, extraction spacing and some role labels demanding. Exact recorded quotations are preserved rather than rewritten.
- The reviewer recognized three reused checklist items but did not establish how checklists are created, approved or maintained. The recorded histories contain no human-reviewed memory edit; no such lifecycle is claimed.
- Document upload, a person correcting the draft and resolving deadline questions were not demonstrated. Intake provenance and the unsent draft are shown; the film does not claim these absent actions occurred.
- All files received means the recorded file set is present, not that every legal requirement passes. The reviewer distinguished that meaning after initial ambiguity.
- No measured accuracy, time savings or real-case handling reliability is established.

## Authority and stop boundary

The user authorized W11 integration and PR21/PR36 coordination, not deployment or inference. No provider, ledger or hosted writes, original-nine rerun or spending occurs. The original-nine grant was consumed on 9 October, 18/18 calls; no remaining allowance exists.

“Before any call, the Mac integration owner checks the ledger to confirm this allowance is still available. This receipt grants no new allowance or retry.”

This is the final UI handoff after the final receipts pass. Subsequent UI work is limited to defects reported by the Mac owner on PR21.
