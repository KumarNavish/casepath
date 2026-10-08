---
version: agent-native-v2
name: CasePath
description: An editorial work surface connecting decisions, process, documents and reviewed knowledge
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

The desk answers who acts next. Five counts precede the claims: Needs you, Agent working, Waiting on others, Quiet and Closed. Quiet and closed groups start collapsed. Every visible ask comes from a verified server projection. A row names the decision, its stop reason, accountable handler and saved agent state, with an explicit Open claim link. The recorded work, source coverage and unsent draft state are visible on first load. Quiet / unreviewed counts identify claims not yet reviewed; an activity completion is explicitly an agent review. “View source and review” opens the supporting detail and exact source passages in place. A claim without a review says so.

The first-minute claim has the display title “Family-home termination notices”. Its original subject, message and source bytes remain available in Sources. Display labels do not change the corpus.

## One document, three views

Overview opens with the agent state, accountable handler, recorded review coverage and unsent draft state. Controls and the mandate share a native disclosure, keeping the handoff first. Recovery controls open automatically when execution needs reconciliation. The mandate lists unattended reading, extraction, derivation and local drafting; handler validation, process changes and external actions remain approval boundaries. Stop and Resume use persisted control events and safe run checkpoints.

One bounded decision leads the working surface; the labelled native selector follows it. The selected question gives typed answers, a marked proposed answer, the agent reading, a counter-reading disclosure and exact source links. The reading and proposed action have different labels. A condition decision names the current process reading (or intake reading before process adoption). If the selected answer matches, it asks for confirmation without a duplicate change arrow. A different answer is compared with the current reading and marked not saved. Values come from existing verified state; the comparison is absent when the condition value is unavailable and for other question kinds. Condition choices explain what the handler records in plain words. Exact source passages sit beside the proposal; the original signed rationale stays inspectable. Display guidance never changes the sealed question, reason or answer sent to the server. Answer explanations expand with the selected answer; the original agent proposal remains marked even when the handler chooses differently. An override requires a reason. Preview keeps the handler answer, agent proposal, counter-reading and exact passages visible with the server-calculated consequences before Apply. On narrow screens, the selected question and answer repeat immediately beside Apply so scrolling through evidence does not remove the decision context. The last saved consequences remain inspectable after the question changes. A request always says not sent.

The decision and its actual process context sit side by side on desktop and in reading order on smaller screens. One selected step appears once, with real incoming and outgoing connections. Its document requirements are attached directly to it, with their current route and review states. Review evidence opens a received document review; Link evidence opens the same exact requirement when evidence is missing. Neither action saves anything. The knowledge link distinguishes available reviewed versions from recorded uses in this claim. A proposed process labels its requirements as proposed. Edited policy steps expose their current review state; historical policy provenance does not certify the edit.

Process exposes the same connected dependency view and a selected-step inspector. Document state, validation, completion and readiness remain separate. The preview lists changes and unchanged nodes, relationships, documents and draft requirements. Undo is a compensating journal event with its own preview and revision checks.

The What-if sandbox keeps its accepted intake baseline explicit. Plain-language, pressed-state choices lead into rule-separated changed requirements with the actual before-and-after applicability or document state. The comparison names its previous and proposed sandbox verdict; the handler note and save action follow beneath. Its reading width, serif heading and spacing match the primary decision surface.

Documents groups graph-derived requirements by Now, Later and Not needed, and presents the current draft. Each linked requirement has a direct source-review action and a stable focus target. Contextual navigation waits for the current verified process and opens the precise node, relationship or document form; a superseded navigation cannot take focus back. Save, copy and local export precede the editable letter. Missing, unreadable, conflicting, held not reviewed, handler confirmed and not applicable use distinct words as well as color. Source conflicts precede agreement. The Sources sheet opens exact bytes and the cited passage; viewing does not accept an observation.

Recent work uses typed persisted milestones. Its inspector uses the same white surface, restrained type and rules, with named links to connected work. Full review trace and journal remain one action away. Reusable knowledge stays in a disclosure. A correction belongs to its claim until a handler previews and approves a scoped lesson or fragment. Applying a pinned version to another claim requires another preview. Version, source, reviewer and each recorded reuse occupy separate readable rows. At desktop widths, saved knowledge sits beside the proposed fragment; smaller screens keep that reading order. Approval displays the exact name, rationale, reviewer, included steps and excluded connections. It creates a new fragment at version 1 and leaves saved versions unchanged. Cross-claim conflicts are explicitly unchecked until reuse review. Cancel reuse closes the preview and returns to the editable preparation form.

Encoded email citations show the verified readable body and highlight the exact cited passage. Original MIME formatting sits in a disclosure and the original file remains downloadable. A failed text or span check never presents an unverified highlight as exact evidence.

## Typography and structure

Self-host Merriweather Light for display text and Open Sans for body text. Their SIL Open Font License files ship with the assets and are credited in THIRD_PARTY_NOTICES.md. Fonts and all application assets load from the local origin.

Use a white page, near-black text and hairline rules. Primary decision prose is at least 13 px; compact metadata uses 11–12 px. Body copy and control labels carry the reading hierarchy. Burgundy identifies active choices, unresolved asks and focus. Green identifies reviewed or received state. Amber is reserved for unresolved evidence. Always write the state. Numbers use tabular figures. Avoid decorative cards, shadows, gradients, avatars and confidence percentages.

The desk is at most 1240 px wide with 36 px side padding. Below 540 px, its counts use a three-plus-two arrangement with 12 px labels; the first claim remains fully visible at 390 × 844. Its heading and count bands leave room for the first decisions in the initial viewport. Scan rows are denser than reading sections. Expanded checks align beneath the claim instead of forming a detached right-hand block. The claim reads within 1100 px; long prose is constrained further. At narrow widths, reduce padding and stack controls. At 540 px and below, the claim panel owns one vertical scroll region; its workspace and work column expand within it. Refresh and tab navigation preserve that actual scroll region. Use normal wrapping, including filenames and selected question text. Sources becomes a sheet rather than forcing the work column sideways. When sources share the desktop, the claim header uses the narrower reading arrangement; opening Controls gives it the full remaining column width. The header responds to the source-panel state as well as the viewport. Source navigation is a native disclosure above the open document. Following a citation closes the file list, keeping the active source heading and exact passage together; opening the source library remains an explicit keyboard-accessible action. Read refreshes preserve the disclosure.

## Motion and recovery

A deliberate decision change introduces its new process context with a 180 ms opacity and transform transition. Repeated renders and background reads do not trigger it. A real returned preview fades into place in 180 ms. Its Proposed cells enter from an 8 px offset while Current stays still, drawing attention to the saved-to-proposed comparison. Existing process changes show their dependencies and Current → Proposed impact. Animate transform and opacity only. The shared transition rule also limits inherited controls to those properties; source emphasis uses an opacity fade. Reduced motion removes animations and transitions. No spinner, typing effect or simulated progress represents agent work.

Loading occupies the shape of the incoming content. Read failures retain saved content where available and give a retry action. Ambiguous writes preserve their exact body and idempotency key for recovery; a definitive rejection clears the pending command. A stale preview preserves the answer and reason while requiring a new preview. Polling preserves open peeks, supervision controls, the mandate, counter-readings and keyboard focus. Background claim refreshes restore the active reason and caret only while focus is still lost to the replaced view; they never take focus back after the handler moves elsewhere. Replayed desk arrival refreshes agent work without replacing an unchanged claim form. Work polls update the agent projection without rebuilding the whole claim. A failed save scrolls its exact-request recovery control into view. Deferred fragment navigation opens and focuses the library once its verified view arrives.

A verified, interrupted local process-node proposal offers Review interrupted step. Its approval names the exact step and requires a recovery note. Reconciliation reconstructs the recorded local proposal under unchanged source, process and journal guards. It leaves the working process unchanged and requires a separate Resume. Provider calls, unknown effects and live work retain their inspection boundary. A superseded recovery request never reports successful reconciliation.

## Keyboard and authority

Use native links, buttons, radio groups, select controls and disclosures. Maintain visible 2 px burgundy focus, labelled inputs and status announcements. Main-navigation and source-close links have a minimum 32 px target height without extra button decoration. Input boundaries use the darker control-line token; decorative layout rules stay quiet. Desk section anchors and focusable claim links leave space below the fixed header. Claim tabs support arrow keys. Dialogs keep focus, Escape closes them, and the return target stays visible. Inactive panels are inert.

Technical details preserve the open dialog, focused identity summary and expanded evidence receipts through a read refresh. Dynamic receipt content is rebuilt from the validated state before its disclosure state is restored.

The hash-chained journal owns lifecycle authority. Agent runs own progress evidence only. The browser verifies sealed projections and never derives readiness. Process completion does not approve settlement, denial or a legal outcome. Local deterministic mode has no provider calls or sending.

Claim controls, the larger claim presentation and the work-motion module load only when a claim opens. All three are local, hash-bound assets; a failed or incomplete load gives a retry and never renders a partial claim. Concurrent entries share their loads while the latest claim alone can appear.

The decision context is explicitly labeled **Saved process** (or **Proposed
process** before adoption). Unsaved answers never relabel that graph. An
unresolved branch reads **Possible branch**, retaining its actual condition and
uncertainty. Saved handler edits show their separate step-validation state.
The desk names unreviewed work before quiet work so inactivity is not confused
with a completed review.
## Recorded live review

On a fresh visit, completed review appears in a disclosure below the handler
decision. A current run observed working opens its review above the decision
and keeps that position through completion, so incoming results do not move the
reader's active surface. Closing that disclosure or beginning a fresh visit
releases this per-run presentation anchor. It changes no saved run state.

A completed review gives priority to a recorded required document and the exact process step linked to it. Its source passage remains independently cited; the display never invents a source-to-step relationship. The actual last event remains available separately from this selected detail. Closing a completed disclosure preserves its own keyboard focus when moving it below the decision.

Four compact stage buttons name Sources, Findings, Process and Documents. The
selected stage shows its count and status once below the buttons; accessible
button names retain both. Completed stages say **Review recorded**, which does
not imply source truth or process validation. The rail describes review stages;
only verified recorded relations connect a process step to a document.

New visible milestones may enter once with a 180 ms translation and opacity
transition, with a 220 ms line reveal. Existing history, a cold load, keyboard
interaction, hidden content, and reduced-motion preferences remain still.
Streaming events invalidate the view; a verified saved projection supplies all
displayed facts. Open claims keep a quiet verified read after completion so a later draft receipt also reaches the screen. Native disclosure activation is retained synchronously through incoming renders, and replaced elements cannot change the current disclosure state. Connection loss preserves the last verified view and typed
input, with a quiet recovery notice and periodic rereads.

Live model review is an explicit claim action within the existing **Controls**
disclosure. Its per-review ceiling accompanies the button; **Review details**
exposes the configured model and synthetic-source scope. Optional paid reruns
stay with these controls rather than preceding the handler decision. Keys remain server-side. The normal launcher
has no model dependency or spend. A stopped external request is not resent;
clearing a safe terminal pause restores the delegate mandate and requires a
separate click to begin another paid review. Summaries describe inspectable
work and citations; private provider reasoning is neither displayed nor stored.

At the 8 October 2026, 11:38 UTC source-edit checkpoint, the built reference UI
has a saved 390×844 check: no overflow, decision action bottom at 823.17 px,
44 px stage buttons, and unchanged decision document position when history
opens. This does not verify the configured paid-control layout or actual
provider motion. The prior full suite found one packaging omission; its focused
repair and the 244-test frontend pass are recorded in the acceptance document.
Final sealing, full-suite acceptance, paid execution and award-quality review
remain separate gates.

Unchanged claim Controls stay attached during live work updates so pointer and keyboard actions can complete. Metadata and recorded findings may refresh around them. On narrow screens, decision spacing leaves room for a 44 px primary action while retaining the exact supporting passage.

A saved source reading can still await a handler. A matching condition proposal says Awaiting your confirmation, so a persisted reading does not imply handler approval.

Completed work that remains above a pending question includes an explicit Go to decision action. It moves focus to the decision only when activated and preserves the expanded work record. Refresh never moves focus for the handler.
