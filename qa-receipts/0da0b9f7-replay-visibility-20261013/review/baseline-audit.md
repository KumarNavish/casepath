Focused visibility/replay baseline audit

Base: bc0ddb5340e4251360ee0f4dcb960ddb190a4114
Branch: codex/casepath-replay-visibility-20261013
Scope: read-only independent review of autonomous-workspace-v1.js, related motion guards, and unified-product-browser-v1.test.cjs.

Findings:
- visibility() invokes pauseInspection() when hidden. This sets inspectionHold and pausePresentation() copies the session into pausedPresentation, clears replayPrefixes, and nulls demoSession. The visible branch never restarts replay. This explains the persistent Resume requirement.
- keyboardInput() accepts synthetic Tab/Arrow events and applies a persistent inspection pause without isTrusted or workspace target checks.
- Replay prefix verification already checks exact current head identity, sequence +1, retained event identity, and chain linkage on consumption. Preserve those checks and the exact in-flight promise when hiding.
- Reset replay displayedAt on visibility restoration to prevent hidden time from reducing the next dwell interval.
- replayTick error, openPresentationCase error, and openClaim resolution paths require hidden-state review; a late result must not paint or hand off while hidden, and an error must remain consumable on restoration.
- Current replayTick/consumeReplay guard sets omit recordDialog.open and inspectionHold; the handoff guard includes both.
- serviceStatus() and loadOpenedClaim() invoke resumeLivePresentation(); retaining a live demo session during hiding could authorize Start after visibility restores fresh authority. Auto-resume must be replay-only.
- Existing tests group hidden with source/navigation persistent cancellation. Hidden needs separate transient suspension assertions while trusted inspection and navigation preserve persistent cancellation.

Commands inspected:
- git status --short; git branch --show-current; git rev-parse HEAD
- AGENTS.md; docs/HYBRID_DEVELOPMENT.md; README.md; docs/PRO_HANDOFF.md; CONTRIBUTING.md
- Relevant sections of autonomous-workspace-v1.js, agent-work-motion-v3.js, unified-product-browser-v1.test.cjs

No source edits, network work, provider access, running servers, or tests were performed for this baseline audit.
