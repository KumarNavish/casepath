# W8 — final refinement evidence

This package follows NS3 approval 6319227767. UI refinements are in `dfb594e`;
font packaging is in `5d85ff4`. It supersedes the earlier W8 frames and keeps
that run's failures for review. It is not a deployment or a completed full gate.

The focused UI suite passes 528 tests. All 35 existing browser regressions pass,
including narrow screens, with no skips. The export fixture repair passes all
26 tests and static packaging passes all 16 tests. The five browser scripts
use built assets with no overrides for the final receipts. They cover every
recorded case and step, grouped sources, exact passages, requests quoted from
the message, documents, drafts, reasoning, History, checklist reuse, motion,
reduced motion, reload and Back/Forward. Any receipt must say `passed: true`;
a missing or partial receipt is not a pass.

Memory cards are centred on the selected node, clamped between the first node
and the notice margin (y180–763 at 1440×900). One level 1px crimson rule joins
the selected node to the source card. The whole cited passage remains visible.
Checklist controls use underlined links. Source checker names each source once.
Claim reader displays Wants only when the extracted request occurs verbatim
in the recorded message source; otherwise it says No facts from this source.

States 1–5 use concept 01, completed process/state 6 uses concept 02, and the
recorded checklist chain/state 8 uses concept 03. State 7/NS4 is omitted because
the recorded DAGs contain no alternatives with consequences. No Before/Now
comparison appears without a recorded step-specific outcome change. Recorded
content, unavailable fields and the actual DAG take precedence over illustrative
concept text. Source text retains its original whitespace; full-source DOM
checks account only for HTML CRLF normalization.

## Gate history and remaining boundary

`initial-gate.json` and `initial-gate.log` bind the full run at `5a8563d`:
2,854 passed, ten failed, ten skipped, ten warnings. Seven failures were export
fixtures placed inside Git; two were Mulish packaging assertions. Both groups
are repaired and their focused tests pass. One failure is the Mac-owned hosted
startup test; its owner-authored correction is `4c46f43`, now integrated unchanged
with `git cherry-pick -x` as `1122d7b` under planner permission 6320266952.
The targeted startup check is captured in `owner-startup-test.log`. `mac-owned-test-failure.log` is the independent
reproduction. `interrupted-gate.json` and its log retain the duplicate rerun
stopped after that deterministic ownership blocker was identified.

The ten skips require one unavailable frozen independent-transition packet and
nine unavailable saved native source-binding runs. No frontend suite was
skipped. The owner correction passes its targeted check and the updated source is sealed.
A final strict pass is still required before READY FOR MAC. The completed gate
will be bound to its frozen SHA, full counts and log digest in that PR #21 post;
this evidence package is not recommitted after the gate. The planner
then runs its independent gate at that exact SHA; source stays frozen during it.

## Reproduction

Use a fresh full clone, then `./bin/casepath prepare` before the strict gate.
Preparation supplies the sealed artifact inventory and isolated runtime. The
launcher rejected a linked Git worktree because it requires canonical Git
authority; no launcher checks were bypassed.

```sh
CASEPATH_REQUIRE_FRONTEND_SUITES=1 \
CASEPATH_NODE="$(command -v node)" \
NODE_PATH="$PWD/casepath-qa/node_modules" \
PLAYWRIGHT_EXECUTABLE_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' \
./bin/casepath test
```

The owned preview is GET-only on port 4180. Browser scripts block and record
non-GET/HEAD requests and capture console/page errors. The immutable nine-case
fixture was not recaptured. No paid inference, hosted writes, original-nine
rerun, merge or deployment occurred. Port 4173 remains untouched.
