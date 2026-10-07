---
version: agent-native-v2
name: CasePath
description: Editorial desk and supervised agent workspace
colors:
  white: '#ffffff'
  ink: '#242522'
  muted: '#666862'
  rule: '#dedfd9'
  control_line: '#85877f'
  burgundy: '#85263c'
  green: '#2f624b'
  amber: '#805700'
---

## The job

The desk answers who acts next. Five counts precede the claims: Needs you, Agent working, Waiting on others, Quiet and Closed. Quiet and closed groups start collapsed. Every visible ask comes from a verified server projection. A row names the decision, accountable handler and saved agent state, with an explicit Open claim link. Quiet / unreviewed counts identify claims not yet reviewed; an activity completion is explicitly an agent review. “What was checked” opens source coverage and the latest persisted activity in place. A claim without a review says so.

The first-minute claim has the display title “Family-home termination notices”. Its original subject, message and source bytes remain available in Sources. Display labels do not change the corpus.

## One document, three views

Overview puts the accountable handler above the CasePath agent, marked Delegate. The header gives the recorded role and original-source coverage counts immediately. Historical reviews are labelled. The mandate lists unattended reading, extraction, derivation and local drafting; handler validation, process changes and external actions remain approval boundaries. Stop and Resume use persisted control events and safe run checkpoints.

A labelled native selector chooses one bounded decision. The selected question gives typed answers, a marked proposed answer, the agent reading, its counter-reading and exact source links. The reading and proposed action have different labels. An override requires a reason. Preview keeps the handler answer, agent proposal, counter-reading and exact passages visible with the server-calculated consequences before Apply. On narrow screens, the selected question and answer repeat immediately beside Apply so scrolling through evidence does not remove the decision context. The last saved consequences remain inspectable after the question changes. A request always says not sent.

Process exposes the executable dependencies and a selected-step inspector. Document state, validation, completion and readiness remain separate. The preview lists changes and unchanged nodes, relationships, documents and draft requirements. Undo is a compensating journal event with its own preview and revision checks.

The What-if sandbox keeps its accepted intake baseline explicit. Plain-language, pressed-state choices lead into rule-separated changed requirements with the actual before-and-after applicability or document state. The comparison names its previous and proposed sandbox verdict; the handler note and save action follow beneath. Its reading width, serif heading and spacing match the primary decision surface.

Documents groups graph-derived requirements by Now, Later and Not needed, and presents the current draft. Save, copy and local export precede the editable letter. Missing, unreadable, conflicting, held not reviewed, handler confirmed and not applicable use distinct words as well as color. Source conflicts precede agreement. The Sources sheet opens exact bytes and the cited passage; viewing does not accept an observation.

Recent work uses typed persisted milestones. Its inspector uses the same white surface, restrained type and rules, with named links to connected work. Full review trace and journal remain one action away. Reusable knowledge stays in a disclosure. A correction belongs to its claim until a handler previews and approves a scoped lesson or fragment. Applying a pinned version to another claim requires another preview. Version, source, reviewer and each recorded reuse occupy separate readable rows.

## Typography and structure

Self-host Merriweather Light for display text and Open Sans for body text. Their SIL Open Font License files ship with the assets and are credited in THIRD_PARTY_NOTICES.md. Fonts and all application assets load from the local origin.

Use a white page, near-black text and hairline rules. Primary decision prose is at least 13 px; ownership and navigation metadata stay at least 12 px. Burgundy identifies active choices, unresolved asks and focus. Green identifies reviewed or received state. Amber is reserved for unresolved evidence. Always write the state. Numbers use tabular figures. Avoid decorative cards, shadows, gradients, avatars and confidence percentages.

The desk is at most 1240 px wide with 36 px side padding. Its heading and count bands leave room for the first decisions in the initial viewport. Scan rows are denser than reading sections. Expanded checks align beneath the claim instead of forming a detached right-hand block. The claim reads within 1100 px; long prose is constrained further. At narrow widths, reduce padding and stack controls. Use normal wrapping, including filenames and selected question text. Sources becomes a sheet rather than forcing the work column sideways.

## Motion and recovery

A real returned preview fades into place in 180 ms. Its Proposed cells enter from an 8 px offset while Current stays still, drawing attention to the saved-to-proposed comparison. Existing process changes show their dependencies and Current → Proposed impact. Animate transform and opacity only. The shared transition rule also limits inherited controls to those properties; source emphasis uses an opacity fade. Reduced motion removes animations and transitions. No spinner, typing effect or simulated progress represents agent work.

Loading occupies the shape of the incoming content. Read failures retain saved content where available and give a retry action. Ambiguous writes preserve their exact body and idempotency key for recovery; a definitive rejection clears the pending command. A stale preview preserves the answer and reason while requiring a new preview. Polling preserves open peeks, the mandate and keyboard focus. Background claim refreshes restore the active reason and caret only while focus is still lost to the replaced view; they never take focus back after the handler moves elsewhere. Replayed desk arrival refreshes agent work without replacing an unchanged claim form. Work polls update the agent projection without rebuilding the whole claim. A failed save scrolls its exact-request recovery control into view. Deferred fragment navigation opens and focuses the library once its verified view arrives.

## Keyboard and authority

Use native links, buttons, radio groups, select controls and disclosures. Maintain visible 2 px burgundy focus, labelled inputs and status announcements. Input boundaries use the darker control-line token; decorative layout rules stay quiet. Desk section anchors and focusable claim links leave space below the fixed header. Claim tabs support arrow keys. Dialogs keep focus, Escape closes them, and the return target stays visible. Inactive panels are inert.

Technical details preserve the open dialog, focused identity summary and expanded evidence receipts through a read refresh. Dynamic receipt content is rebuilt from the validated state before its disclosure state is restored.

The hash-chained journal owns lifecycle authority. Agent runs own progress evidence only. The browser verifies sealed projections and never derives readiness. Process completion does not approve settlement, denial or a legal outcome. Local deterministic mode has no provider calls or sending.
