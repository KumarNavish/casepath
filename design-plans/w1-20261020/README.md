# W1 — simpler recorded work

Updated by the [21 October planner revision](../w1-20261021-revision/README.md). The evidence below records the original W1 submission.

Base: `a59cff2bbdd8e4a339e574ad18d64f2e52710feb` (`claude/casepath-cues-prototype`). Target: `claude/casepath-agents-20261019`. Worker: `codex/casepath-ui-w1-20261020`, isolated Mac clone, task `01a15ae9-3851-79b2-9d1b-af0b75f25a86`.

Implements W1 and [planner Addendum 1](https://github.com/KumarNavish/casepath/pull/21#issuecomment-6301459970). The original colours, typography, page background and hairlines remain.

- Three demonstration header rows: title, customer question, one transport row. Choose case and History appear once. Provenance remains in the quiet mode disclosure; the guide appears when paused, including a keyboard pause.
- The source passage carries the current action. Upcoming steps show only their titles. Active/completed facts stay on one line, with the full chip quote on hover or focus. A received document is one flat source line.
- A 16×2 px green rule transfers the source cue without covering labels. Passage emphasis and transfer run sequentially. Automatic following no longer adds a concurrent smooth scroll; desktop following keeps the case title visible.
- The answer has three primary rows: result, Documents, Next. Why holds exact recorded wording, citations, limits, legal basis and reuse. Original record objects, source bytes and History remain available.
- Recorded summaries/issues stay inside Why as required by the three-row answer. The no-gap next action no longer names absent documents. The existing roster is retained; the planner assigned roster consistency to W2.
- Includes the Mac owner's requested gate patch `9e854ea2`: TAP reporter, skip reasons and correct flock exit codes. The Mac-owned passive-startup test is untouched.

## Visual evidence

The same copied database holds all nine complete deterministic reference histories (v1 then v2). No model calls were made. Before uses the three exact prototype assets. Final captures use the sealed build without asset overrides. Fixed-time captures measure time after navigation settles, not cold-load speed; scheduling can place them at different recorded operations.

| View | Before | After |
| --- | --- | --- |
| Desktop, 6 seconds | [Before](before/demo-06s.png) | [After](after/demo-06s.png) |
| Desktop, 12 seconds | [Before](before/demo-12s.png) | [After](after/demo-12s.png) |
| Desktop, 18 seconds | [Before](before/demo-18s.png) | [After](after/demo-18s.png) |
| Desktop, 24 seconds | [Before](before/demo-24s.png) | [After](after/demo-24s.png) |
| Phone, 390×844 | [Before](before/mobile-demo-12s.png) | [After](after/mobile-demo-12s.png) |
| Completed rent case | [Before](before/claim.png) | [After](after/claim.png) |
| Documents | [Before](before/claim-docs.png) | [After](after/claim-docs.png) |
| Completed heating case | [Before](before/claim-heating.png) | [After](after/claim-heating.png) |

**Count test:** the [planner's supplied baseline](../cues-20261020/before-demo-12s.png) has **48** detected text regions; the [matching checker/heating-report frame](after/demo-matched-heating.png) has **25**, a **47.9% reduction** at 1440×900. Both show the same recorded document check and exact `15.8C` passage. The count uses offline Apple Vision accurate OCR with identical settings, one detected text region per element. It is a reproducible visual proxy, not a DOM-node count. [Baseline regions](checks/text-before.json), [matched regions](checks/text-matched.json), [counting script](../tools/count_frame_text.swift).

**10-second frame review:** in the [matched frame](after/demo-matched-heating.png), the customer asks about repeated heating failure; Checker checks the heating service report; the highlighted words are `15.8C`; that document check is confirmed, while the final repair/reduction step is still open. The [10-second capture](after/demo-10s.png) and [completed answer](checks/w1-1440-result.png) provide the in-progress/result comparison. This is an executor reading of the frames; first-time human acceptance remains with the planner.

## Verification

- **465 focused frontend tests pass, zero failures/skips:** 431 workspace/language/entry/product tests and 34 evidence-identity browser tests. Node 26.8.2, the repository's locked Playwright package, installed Google Chrome.
- [Live geometry and motion checks](checks/checks.json): 1440×900 and 390×844; cue ≤16×2 px; chip height 44 px; at most one animation; no duplicate controls or visible upcoming facts/documents; zero horizontal overflow, page errors or attempted non-GET/HEAD requests. Desktop title clearance is at least 30 px. Why starts closed and exposes the full answer when opened.
- [Keyboard and reduced-motion checks](checks/access.json): full chip quote on focus, guide on keyboard pause, exact quote in its record, Escape restores the opener, zero animations under reduced motion, no errors/writes. [Focused quote](checks/focused-quote.png), [reduced-motion phone](checks/reduced-motion-phone.png).
- [Exact cited source inspection](exact-source.png) and [empty main workspace](empty-main.png) record the separate source-opening and honest unrun checks. Final source/receipt details are in [verification.json](verification.json).
- The final native empty-workspace boot required restoring its recorded runtime inventory: 846 added bytecode-cache paths were quarantined; all recorded package files matched, with none missing. Boot records were preserved. Direct Node tests should set `PYTHONDONTWRITEBYTECODE=1` for their Python fixtures.
- Source generation, static build and source-manifest verification cover **1,723 files**. Final manifest hash and gate outcome are recorded in verification.json.
- The strict five-suite frontend gate and the five tests for the imported gate fixes are run in a cleared, isolated environment. Their receipt is in verification.json.
- The complete deterministic suite and all 24 Mac findings belong to W5 under the planner’s latest assignment. Preliminary full-suite runs were interrupted as W1 changed; none is counted as a full pass. The separate Mac startup-test fix remains an integration dependency.

Commands:

```sh
PYTHONDONTWRITEBYTECODE=1 node --test --test-reporter=tap casepath-qa/autonomous-workspace-v1.test.cjs casepath-qa/autonomous-language-v1.test.cjs casepath-qa/sites-autonomous-entry.test.cjs casepath-qa/unified-product-v1.test.cjs
PYTHONDONTWRITEBYTECODE=1 PLAYWRIGHT_EXECUTABLE_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' node --test --test-reporter=tap casepath-qa/autonomous-evidence-identity-v2.test.cjs
BASE=http://127.0.0.1:4180 PLAYWRIGHT_EXECUTABLE_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' node design-plans/tools/check_w1.mjs design-plans/w1-20261020/checks
BASE=http://127.0.0.1:4180 PLAYWRIGHT_EXECUTABLE_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' node design-plans/tools/check_w1_access.mjs design-plans/w1-20261020/checks
CASEPATH_NODE=/usr/local/bin/node NODE_PATH="$PWD/casepath-qa/node_modules" PLAYWRIGHT_EXECUTABLE_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' CASEPATH_REQUIRE_FRONTEND_SUITES=1 ./bin/casepath test
```

## Limits and next gate

W1 only, including the planner's addendum. W2–W5 have not started. The existing phone follow behaviour can move the case title out of view; W4 owns the phone story/sticky Now work. These checks do not establish W5's exhaustive nine-case interaction acceptance or a hosted release.

The [Mac review list](https://github.com/KumarNavish/casepath/pull/21#issuecomment-6291647001) remains an integration checklist. W1 addresses the answer disclosure, no-gap copy, focus-ring clipping and required gate fixes. Per the [planner’s assignment](https://github.com/KumarNavish/casepath/pull/21#issuecomment-6302005554), W2 owns default-roster consistency and the model-wording check; W5 must resolve or explicitly answer all 24 Mac findings. This is not a claim that all 24 findings are closed. The Mac owner retains `ac5ec61c` for the stale passive-startup test at integration.

No provider calls, hosted writes or deployment occurred. The previously consumed nine-original allowance was not repeated. After the item PR is ready, report `CODEX W1 READY` on #21 and wait for explicit `APPROVED W1` before W2.

Correction, 2026-10-21: the allowance-consumed statement above has no linked consumption receipt. Before any call, the Mac integration owner checks the ledger to confirm the separate nine-original allowance is still available. This receipt grants no new allowance or retry. Codex performs no paid inference or original-nine run.
