# W11: final UI and reliability handoff

The superseding [PLANNER W11 instruction](https://github.com/KumarNavish/casepath/pull/21#issuecomment-6364491895), explicitly adopted by the user, puts hosted read reliability first and retains the checklist and north-star requirements. It supersedes `60d4907ca5c975e288fa3c0973992abd31fcc594`. After the verified PR21 handoff, no further changes are permitted except defects the Mac owner reports on PR21. Release remains with the Mac owner.

## Recovery and completion on 23 October

The ChatGPT Commander continuation recovered Codex thread `01a15ae9-3851-79b2-9d1b-af0b75f25a86` after its usage-limit stop. The original W11 UI checkout and unfinished reliability checkout remain preserved. The successor branch starts at `d6f42041a83bb27558fe931ea84b43b1b897254f` and carries the recovered reviewed patch. The earlier UI-only strict gate passed, but its final walk has no completed acceptance receipt; it is retained as interrupted evidence and is not substituted for this candidate's gate.

With generated synthetic fixtures present, the recovered patch passed 188 focused backend tests and 365 frontend tests. Final acceptance still requires the complete strict gate on the newly sealed source and the serial browser walk. An added regression demonstrated that an unknown-case 404 incorrectly erased the healthy Knowledge fallback. Unknown-case HTTP 404 failures now evict only their exact cache key; HTTP 409/422 saved-state validation failures and other integrity/protocol failures still invalidate the entire cache. The original failing regression and the two integrity-failure regressions are retained; the corrected reliability and protected read-only suites pass all 34 tests. The changed workspace script's existing `sha256` query in `casepath/index.html` is updated to its exact content digest; the comparison admission permits only that digest substitution in the otherwise unchanged index.

A separate fresh viewer again recognized the source-to-assessment flow, human review boundary and reuse of three checklist items with new case facts. Its remaining limits are retained: dense extracted source text, a subtle later-case transition, no demonstrated knowledge-approval lifecycle, and no measured accuracy or time savings. The recorded quotation bytes and approved presentation remain unchanged.

The current user requested recovery and completion for a reliable demo. This continuation performs the Mac follow-up release only after the candidate's required gates pass, preserves the existing public read-only audience, and verifies aligned API/site identity and the required published read soak. It grants no inference, model runner, research rerun, provider call or new spending.

## Hosted read reliability

The immutable public Claims, Knowledge and JSON claim-history projections retry classified primary-storage ReadTimeout/connect failures and Hrana 5xx responses. There are at most three total attempts under one ten-second read budget, including database calls, lock waits and response encoding checks. The two possible inter-attempt waits use jittered 100/300 ms backoff; the requested 900 ms schedule entry never creates a fourth attempt. Each HTTP phase is capped at two seconds or one quarter of the remaining budget. The Sites proxy deadline is fourteen seconds. Existing HTTP connections remain pooled and reused.

A retry runs the complete validated projection with fresh transactions. A transport guard admits only BEGIN, SELECT, COMMIT and stream close inside that read scope. It rejects writes, scripts and multiple statements before transport. Private writes and NDJSON operation streams have no retry or projection-cache path. A lost write acknowledgement remains uncertain and is never replayed.

After transient attempts are exhausted, an app-local cache can return the last fully validated and encoded body for that exact endpoint, source commit and all validated path/query/cursor arguments. It is bounded to 64 entries, 16 MiB of bodies, 8 MiB per body and 4 KiB per key. The internal `X-CasePath-Read-Source` header distinguishes `primary` from `last-verified`; both remain `no-store`. Logs retain only endpoint templates and failure categories. Integrity/protocol failures remain fail-closed and invalidate the projection cache. No cached copy means the existing honest 503 response.

The public UI retries an eligible failed JSON read once inside the original request owner and fifteen-second deadline. Cancellation, navigation, schema errors, rate limits, mutations and operation streams do not retry. After exhaustion, polling and visibility changes cannot restart a failed public history read; a calm Try again action remains available. Successful responses, including server fallback responses, keep the existing rendering.

Focused MockHrana tests exercise recovery after a lost BEGIN response, persistent failure, exact cached projections, row neutrality, write exclusion, protocol failure, cache bounds and deadline-aware locks. Frontend tests cover one retry, shared owners, cancellation, a single deadline and terminal manual recovery. Original focused logs, including fixture-setup failures, are retained in the final evidence; successful focused checks do not replace the full sealed gate. The protected Mac-owned tests, including owner commit `4c46f43`'s row-neutral startup contract, remain unchanged.


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

The accepted UI capture and its proof remain unchanged. The final source also contains the reviewed hosted reliability implementation and frontend failure-path handling, so its JavaScript and API bytes are explicitly different. A separate source-bound comparator must replay all 5,283 frames and match every original frame-index digest, then pass six exact live comparisons and complete playback. It records the complete reviewed source delta, separate captured/final asset hashes and full cleanup. This establishes that the retained film still depicts the final source without rewriting the original capture receipt. The unchanged rendering assets, recorded fixtures, geometry audit and protected tests are checked independently. Any changed frame requires repair and, when the checklist presentation changes, recapture and renewed cold review.

The first sealed source `fa2b8ca8c480dcf28fd0cd82f5fecef8922dd10a` passed 2,866 strict tests with ten historical skips. Its walk first stopped before browser launch because the continuation phase used an unsupported name. After correcting that runtime bookkeeping, the walk exposed an obsolete assertion: it expected the current group to keep spinning at fact-rest, after the operation had completed. W11 correctly makes a group with future operations wait, or marks a fully completed group done. The verifier now derives every row state and progress from the recorded group and exact current operation, checks one active row at passage-rest and zero at fact-rest, and safely handles a removed progress bar. Existing geometry, source/fact binding and zero-animation checks remain.

Both failed attempts and the original strict result are retained in [superseded evidence](final-gate/superseded-fa2/). Final acceptance requires a new full strict gate and a fresh complete walk on the repaired, sealed source; the prior strict result is not substituted. That verifier repair changed no product or capture byte. The later combined reliability source requires the independent visual comparison described above and another full strict gate and complete walk; neither earlier gate is substituted.

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

This is the final UI and reliability handoff after the final receipts pass. The Mac owner then performs one follow-up release and a published API/site read soak: at least 300 sequential Claims, Knowledge and history reads, with zero 503s required. This offline handoff does not claim that live soak has passed. Do not repeat the original-nine run. After handoff, further work is limited to defects reported by the Mac owner on PR21.
