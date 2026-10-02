# Visual workspace and motion — 2 October 2026

Operation: `casepath-visual-motion-20261002`. Starting commit: `ec342fcb1ef55bdeb8a473c66b53272a8d49ddf4`. This iteration responds to the request for a more visual, intuitive workspace with purposeful motion. It preserves the existing tabs, editable causal model, source receipts, journal and deterministic local runtime.

## Implementation

- Conflicting original values sit side by side, each linked to its exact source passage. Their comparison does not decide legal validity or calculate a deadline.
- Documents show a file/status marker, a distinct review state and the process step that requires them. Later and inactive requirements are disclosed on demand. Received remains separate from sufficient.
- Process relationships use the actual directed graph and evaluated connection state. The selected step shows only its immediate context.
- Impact comparisons distinguish saved Current values from Proposed values, including semantic edits that leave execution status unchanged. Applying remains an explicit verified command.
- A small shared Web Animations controller uses transform and opacity: 180 ms for work/pane feedback and 220 ms for source drawers. It cancels on keyboard use, reduced motion and hidden pages. Interrupted entrances continue from the current visual state.
- Agent activity animates only new persisted run/sequence pairs. Reopening a saved review does not replay progress.

UI Skills used `emilkowalski/animate` with local `fixing-motion-performance`, building on the preceding Distill/Polish iteration. No runtime dependency, paid inference or external deployment is added.

## Acceptance evidence

Local synthetic claim: `clm_f69b1747447bc221`. Ego task space 54 opened the live application but repeatedly timed out on screenshot capture. The in-app browser provided visual inspection and screenshots. Browser QA used the sealed immutable source capsule; later source repairs were covered by focused regression and the final runtime readback.

| Check | Observed result |
|---|---|
| Original source comparison | 30 June and 31 July appear beside their original filenames. The first link opens the tenant PDF and exact candidate passage `30. Juni`. |
| Unfinished edit | Meaning, actor and reason survive Documents → Sources → Process. Preview retains the new meaning while showing unchanged execution state and zero changed requirements; Keep current process leaves the saved graph unchanged. |
| Branch correction | Family-home true → false previews 6 changed steps, 4 changed requirements and 7 affected connections. Apply persists graph revision 9. The spouse requirement becomes not needed and the earlier draft is invalidated. |
| Impact distinctions | Current and Proposed are separate columns. Connections and additional semantic fields are disclosed; one Apply/Keep pair remains above the comparison. Requirement changes are distinguished from document metadata changes. |
| Live motion | Instrumenting native `Element.animate` records 180 ms opacity/translateY for a pane and 220 ms opacity/translateX for the source drawer. The instrumentation was removed afterward. |
| Reduced motion | Emulating reduce produces no WAAPI calls for Process → Documents. The correct single pane remains visible. Preference override was reset. |
| Rapid interruption and keyboard | Process → Documents → Process leaves one visible pane; the interrupted entrance resumes from its current matrix/opacity. End focuses Documents and cancels running animations. |
| Narrow screen | At 390 × 844 the page and work column are 390px; Process is 358px. Date comparison and directed relationships remain readable without horizontal overflow. Temporary viewport override was reset. |

Independent reviews caught and repaired: an insufficient review hidden behind timing; identical source excerpts incorrectly separated by an inequality sign; ambiguous Requires direction; a cross-claim saved-feedback race; a dependency recalculation described as a source review; and ambiguous empty prerequisite wording.

## Executed checks

- `node --test casepath-qa/*.test.cjs`: **101 passed**, no failures. Includes interruption, event deduplication, reduced motion, mounted form retention, source comparison escaping, review-state distinctions, directed evaluated relationships and semantic impact changes.
- JavaScript syntax checks and `git diff --check`: passed.
- Eager workspace JavaScript: **299,335 bytes**, below the existing 300,000-byte limit.
- Exact asset hashes and source manifest regenerated with the repository sealing commands. Runtime is deterministic reference mode with no provider credential.

This frontend-only iteration did not rerun the broad backend suite. The earlier 55-test causal integration result belongs to the preceding focused UI iteration, and the 1,639-test full-suite result belongs to the earlier causal implementation.

The first browser save wait expired while the request was completing; subsequent inspection confirmed revision 9 and successful recalculation. The save was not retried. No formal screen-reader audit, measured rendering-frame benchmark, real-claim evaluation or customer usability study was performed.
