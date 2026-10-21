# W8 Mac review correction

This revision implements planner comments 6321748940 and 6321925670. The prior
sealed head `011f3dcec0c20cf4f6951a4b32946151a415b4de` passed its strict gate
with 2,864 passed and ten known historical-packet skips. Its log and receipt are
preserved here as `previous-full-gate.*`. The planner's independent gate could
not run because its own gate script was missing; no independent pass is claimed.

The live spine and plan now share the current recorded node. A 1.5px dashed SVG
ring avoids browser rounding of fractional CSS borders. Node-bound, source-pinned
fact extractions join the source Read row. Rows are ordered by first operation;
their state and progress bar depend on completed recorded operations, never time.
All recorded sequences in all nine cases are checked for state, bar progress and
plan-title/ring agreement. Shared and unlinked operations remain outside plans.

Recorded labels appear whole in equal-height cards with room for three lines.
Only unlabelled exact quotes use the explicitly approved three-line ellipsis;
the full quote remains in DOM text, hover title and source highlight. Fact cards
do not scroll. The dotted connector stays hidden before the card arrives and
starts at its actual right edge. Playback holds briefly at the completed passage,
fact and accepted-node states so they can be read and captured at rest. The
running row's spinner runs only between the serial source/fact motions.

Six browser scripts cover the first live source/fact frames in every case, every
completed process node, every memory node, role views, full source content,
documents, drafts, reasoning, History, reload/Back/Forward, motion and reduced
motion. Final receipts use built assets with `overrides: false`. Every per-case
overlap count is reported in `verification.json`; missing or failed checks are
not treated as zero. The role cursor's coarse box is excluded from the generic
box audit, while the motion script separately tests its badge against actual
source-text ranges. No non-GET/HEAD request is allowed.

The side-by-side images show each concept on the left and the product on the
right. They are also embedded state by state in
`docs/product/UI_FINISH_RECEIPT_20261021.md`. Pixel differences are comparison
measurements, not correctness scores. Actual recorded text and DAGs take
precedence over illustrative concept content. NS4/state 7 remains omitted: no
recorded alternatives with consequences exist. There is no unsupported
Before/Now outcome claim or expert-review badge.

The owner correction `4c46f43bdfd32c4fe965d0b9593b65d84a0c8c33` remains
integrated unchanged as `1122d7b14ec64e90c5d0bdec11d759e7fbb3c94a`.
No further protected-test or hosted-startup edit is included.

## Final gate protocol

After final proof and source sealing, use a full clone and run:

```sh
./bin/casepath prepare
CASEPATH_REQUIRE_FRONTEND_SUITES=1 \
CASEPATH_NODE="$(command -v node)" \
NODE_PATH="$PWD/casepath-qa/node_modules" \
PLAYWRIGHT_EXECUTABLE_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' \
./bin/casepath test
```

For a read-only browser walk against the final built head, set
`CASEPATH_PROOF_OUTPUT` to an isolated receipt directory and run the six
`verify-*.mjs` scripts. The recorded deployment identity binds each new receipt
to the served source SHA. Leave `OVERRIDES` and `WIP_FAST` unset. The checked-in
frames show the implementation commit; later commits only package documentation,
the source seal and proof.

The completed final gate is bound to its frozen SHA, counts and log digest in
the revised READY FOR MAC post on PR #21. This pre-gate evidence package is not
recommitted after that run. Source stays fixed during the planner's independent
gate. Per 6322252294, only the planner owner restores its gate script. If the
only finding is that the independent gate could not run, retain the same SHA
and repost the same READY only after the user confirms restoration; do not
reseal, rerun, copy or stub the planner gate. Questions go in their own CODEX QUESTION or CODEX BLOCKED post. Review
waiting uses only `design-plans/tools/wait_for_planner.sh`.

No paid inference, hosted writes, original-nine rerun, merge or deployment.
The immutable nine-case fixture and port 4173 remain unchanged.
