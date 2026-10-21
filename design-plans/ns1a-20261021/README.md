# NS1a — shell and static north star 01

Planner authority: PR #21 comments 6315372898, 6315379287 and 6315405780.
Base: approved W6 `aa5df676f25c72dbd2908d257b4ba56edf0c38fa`.
Implementation: `8c8f93d0b013935c32961c872f5de74b58c2dfab`.

The white shell uses locally bundled Mulish (Google Fonts, OFL), sampled crimson
and grey tokens, the five role tabs and a 262px Sources rail. The main paper is
at (298,234), 671×493. The plan starts at (1013,262), width 298. Facts start at
y=761. Case transport stays at the rail bottom. The current source can be
opened in full; previous/next controls inspect already opened sources.

## Evidence and limits

`state1-ready.png` is the mounted app with a fully verified recorded trace,
waiting for Watch the analysis. `state4-recorded-facts.png` is an isolated static
component capture of **case 1, operation 168** (`document.check`). The app is
destroyed before placing that exact immutable prefix. This is the NS1a static
review, not an assertion that the live motion gate has passed. NS1b owns that
MP4 and sequential-motion gate.

- 482 focused tests; 28 existing desktop browser checks pass.
- All nine recordings have exact source pins, real ordered plan operations,
  a recorded completion as each plan's final row, and faithful role mapping.
- Unknown or ambiguous source reads are not assigned to a node.
- Plan operations after that node's completion remain in History.
- Mounted ready state has no synthetic fixture label. W6's retry has a 16px gap.
- No errors, write requests or horizontal overflow. Cursor badge checked against
  actual source text line rectangles; its intentional paper overlay is excluded
  from the broad box-intersection check.

## Fidelity

See `concept01-side.png`, `concept01-overlay.png`, `concept01-diff.png` and
`fidelity.json`. Mean pixel difference is a comparison aid, not acceptance.

Matched: white and sampled accents, Mulish, icons, top-bar/rail/paper geometry,
ring spine, exact passage highlight, cursor and hexagon, fact cards and dotted
connector, compact plan and Work log.

Deliberate: this recording has four source groups, no recorded email header
fields or received dates, no completed nodes at operation 168, a multi-line
citation, and Document finder is active. Repeated source reads remain separate
scrollable plan rows. The cursor badge sits in empty space beside the cited
paragraph rather than covering the following paragraph. No fake reply or
settings controls. Replay transport is at the rail bottom.

Pending: planner review of the question glossary, live motion and first-two-node
MP4 (NS1b), completed canvas (NS2), memory payoff (NS3), final W8 gate.

## Proposed question glossary

Recorded labels remain in each question's hover title. Unknown IDs use their
recorded labels without rewriting.

| Step ID | Question |
| --- | --- |
| dh_intake | What defect is reported? |
| dh_scope | What are the tenancy terms? |
| dh_notice | Did the landlord know? |
| dh_cause | What caused the defect? |
| dh_evidence | Is the defect supported? |
| dh_response | Are repair and rent reduction supported? |
| lt_intake | What notice was received? |
| lt_form | Is the termination notice valid? |
| ri_intake | What increase was received? |
| ri_form | What notice rules apply? |
| ri_reason | Is the rent increase valid? |

The immutable operations have `stage`, not an actor field. The tested table:

| Recorded operation | Role |
| --- | --- |
| source.open/span.read/phrase.match/fact.extract in interpret_reference, or Reader actor | Claim reader |
| those kinds in verify_reference, or Checker actor; verification.check | Source checker |
| rule/process/node/dependency evaluations, document.require, step.complete, knowledge.reuse; native legal fact with rule_refs; Rulebook/Memory actor | Process builder |
| document.check | Document finder |
| decision/answer | Result checker |
| unknown kind | retain previous role; none before the first mapped operation |

The first exact locator belongs to a supporting document. No recorded operation
pins the customer message, so a fabricated first highlight is not introduced.

No paid inference, original-nine rerun, hosted writes, merge or deployment.
