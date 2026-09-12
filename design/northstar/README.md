# CasePath flagship journey

These approved concepts extend the existing CasePath visual system into one
persistent source-plus-canvas experience:

- `01-decision-building.png`: a process decision is formed from exact sources.
- `02-completed-process.png`: the completed handling spine and its local chain.
- `03-reviewed-memory-payoff.png`: the later-claim reviewed-memory seam.

## Product model

The claim source package and the evolving process are the only two primary
objects. The right-hand workspace never changes into a report or a progress
feed. It moves through eight states in place:

1. Ready to analyse.
2. Source opened.
3. Exact passage, field, or image region selected.
4. Source-bound fact extracted.
5. Several facts combined into one accepted process question.
6. Completed process with contextual fact, law, evidence, document, and
   reference objects.
7. Direct graph edit and visible consequence.
8. A later claim uses one expert-reviewed memory and changes one decision.

## Visual system

- Background: true white.
- Text: near-black `#15171a`; secondary text: cool gray.
- Active reasoning: restrained burgundy `#8f1924`.
- Received or expert-reviewed: restrained green.
- Rules: one-pixel cool-gray hairlines.
- Icons: code-native 1.5px line icons with consistent optical size.
- Typography: plain UI sans serif; compact labels; no marketing display copy.
- Containers: open canvas, source rail, document surface, and one local plan.
  No bento grid, glass, gradient, decorative pill, or permanent audit panel.
- Motion: one role cursor, one source, one selection, and one state change at a
  time. The selected source and exact locator become active only after the
  cursor arrives.

## Allowed primary copy

- `Analyse claim`
- `Building “<process question>”`
- `Open full source`
- `Edit decision`
- `Documents <count> missing`
- `Open documents`
- `Retrieved 1 expert-reviewed case`
- `This case used reviewed memory. Qualified review is still required.`

No AI-written explanatory paragraph is allowed on the primary canvas.

## Decision-builder contract

For each accepted process node:

```text
source opens
→ exact locator becomes selected
→ source-bound fact appears
→ additional source steps complete when required
→ facts combine
→ plan reaches complete and recedes
→ accepted node appears
```

The compact plan is derived from returned fact/source relationships. It must
not invent a source read, model action, fact, or conclusion.

## Completed-node contract

Selecting a node immediately shows only its local chain:

```text
source facts → law → current evidence → evidence still needed → relevant reference
```

The exact source preview is the dominant local object. The complete document
model and audit history are on-demand secondary views.

## Release rule

Build and replay the complete deterministic journey locally. Capture the eight
states at 1440×900. Publish only one exact, tested commit after the complete
sequence is coherent.
