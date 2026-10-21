# NS1b — recorded decision-building motion

Base: NS1a `c230a466de27cea989c2febb2855b39ac7ebcc14`.
Implementation: `fb91742ba2f3f1df67d6f3e19a4c872566ff5a2d`.
Planner authority: PR #21 comment 6315405780; continue while review runs.

`first-two-nodes.mp4` records the mounted, sealed, GET-only Demonstration of
case 1 through its first two accepted nodes. All five PNGs come from that live
recording, with no component replacement or invented operations.

## Sequence and data

Source opens → cursor travels to the exact recorded locator (550 ms) → highlight
(250 ms) → fact rises (300 ms) → connector draws (400 ms). On a recorded node
completion, its plan ticks (200 ms), recedes (400 ms), then the node receives its
check (200 ms). The next evaluated node becomes dashed. No two animations run
at once. A new operation cancels the prior cue safely; pause settles a verified
completion. No cursor appears without a checked locator.

The active plan row scrolls into view. A one-fact connector starts at that card;
additional facts extend the chain. Cursor badges move into the gap beside the
paper when the nearby position would cover source text. Previous/next source
controls inspect already opened sources and pause the replay. Resume restores
the recorded source; Work log opens History.

The role table and proposed process-question glossary are unchanged from the
NS1a README. Unknown kinds retain the previous role; unknown node IDs retain
their recorded labels. The recording has stage fields, not actor fields.

## Evidence

- 483 focused tests, including all-nine exact spans, plan membership/order,
  ambiguity rejection, role mapping and delayed visual acceptance.
- 28 existing desktop browser checks.
- The sealed live capture checks every displayed role and span against the
  immutable trace, checks cursor/highlight ordering, records all cue phases,
  and measures at most one running animation.
- Source navigation, pause/resume and Work log checks pass.
- Reduced motion reaches the same verified case-1 answer with no animations.
- No paid inference, original-nine rerun, hosted writes, merge or deployment.

Every frame has a concept side-by-side, 50% overlay, diff and fidelity JSON.
Pixel differences describe different states and recorded content; they are not
an acceptance score.

Matched: NS1a geometry, palette and local font; source cursor, exact highlight,
facts and connector, plan completion before node acceptance.

Deliberate: recorded case content and order, four source groups, longer
multi-line spans, actual roles and completed-node count, no fictitious email
header fields/dates, source reads retained in the scrollable plan, read-only
Watch the analysis and rail transport. The cursor badge avoids source text.

Pending: planner review of NS1a/NS1b and glossary; NS2 completed process,
NS3 memory payoff, optional NS4 only if supported by the records, and W8.
