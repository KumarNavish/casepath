# W8 — final UI and interaction evidence

UI implementation: `8412ab7`, on NS3 `1b61d1a`. Export fixture repair: `ce3a0c3`. This is the final Mac handoff
candidate, not a deployment. The closure map is in
`docs/product/UI_FINISH_RECEIPT_20261021.md`.

526 focused tests and all 35 existing browser checks pass, including the
narrow-screen regressions. The strict full repository gate runs **after this
evidence is committed**, so it binds the actual review head. Its complete
result is recorded in the CODEX W8 READY / READY FOR MAC comment on PR #21,
and locally in `gate-repaired.json` and `gate-repaired.log`. The evidence commit
is not changed after that gate.

Five sealed browser scripts cover the nine recorded cases, every process node,
exact source passages, every grouped source, documents, reasoning, draft,
History, checklist reuse and reload/Back/Forward. A draft copy stays local to
its browser; copying/exporting does not send it. Storage failure retains the
unsaved text. The 150-case catalog, unrun original and empty search stay honest.

The final animation capture uses the recorded operation stream. States 1–5
are ready, source opened, exact span selected, fact connected and node accepted.
State 6 is the completed process and state 8 the source/checklist/result chain.
State 7 is omitted because no recorded alternatives with consequences exist.
No Before/Now comparison appears without a recorded step-specific change.

Matched: approved white/black/grey desk, restrained role/source cues, selected
process questions, source/plan choreography, exact passages, local chain and
recorded checklist reuse. Deliberate: recorded content and actual linear DAGs,
no unsupported review shields, forks, decision editor, added dates or missing
items. Source bytes, including original spacing, remain unchanged. The full-source DOM check accounts only for HTML's CRLF-to-LF conversion. Pending:
planner acceptance, then Mac integration. No merge or public release is implied.

The scripts block and record non-GET/HEAD requests and capture console/page
errors. Final runs use built assets with no overrides. The immutable fixture
was not recaptured. No paid inference, original-nine rerun, hosted write or
deployment occurred. Port 4173 and the Mac-owned public-hosted-read-only test
were not changed.

The initial strict gate at `5a8563d` exposed seven export-fixture path failures: its TMPDIR lives inside Git, where private export output is correctly refused. The test fixture now allocates a private directory outside Git; all 26 export tests pass under the original launcher conditions. Production guards and assertions are unchanged. The full repaired gate is authoritative; the initial gate log remains a failure record. UI source and asset hashes are unchanged by this test-only repair.
