# CasePath product design

CasePath answers one question: **Why is this the right next step for this claim?** A person should be able to move from the action to the active process step, its obligation, the fact or branch still in question, the evidence state, and the original source.

## The claim workbench

The desktop workbench has three places with distinct jobs. The left rail holds the original customer packet. The center shows the active handling path and nearby alternatives. The right side keeps one next action and its trace in view. Evidence, the full process, and recorded work remain available through tabs. At narrow widths, the order is next action, active path, then trace; the original packet opens in a source drawer.

The current process step must stay visible even when a person selects another step to inspect. Selection explores the record; it does not change the authoritative path. After a saved action moves the path, the explanation returns to the new current step.

An opened document is not accepted evidence. Show a passage as accepted only when the saved observation contains it and its source identity matches the original packet. A source statement that selects a branch does not imply that every detail in the notice is established. Unknown, conditional, missing, and uncertain states must remain explicit.

## Visual rules

- Use white for the work surface, deep blue `#244e72` for the primary action and current path, and one muted warm accent for unresolved attention. Keep supporting backgrounds lightly blue-tinted.
- Let type, spacing, and alignment establish hierarchy. Use borders to separate functions, not to turn every item into a card.
- Show one primary action at a time. Keep technical identifiers, rule text, and specialist handoffs behind named disclosures.
- Use short, sentence-case labels. State what an action will do before it runs; distinguish checking a source from sending a request or deciding a claim.
- Use native buttons, tabs, and disclosures with visible keyboard focus. Do not make hover or color the only way to read state.
- Motion may reveal a saved state change, but must stay brief and respect reduced-motion preferences. The interface must remain understandable with no animation.

The review record is secondary to the claim decision. It shows actual saved work and handoffs on demand; it never turns a completed review into a completed claim.
