# Three agent-native references for a calmer CasePath

Research retrieved 2 October 2026. This is a bounded product-design study, not a performance benchmark or a claim that these are the world's three best interfaces. The chosen products are **OpenHands Agent Canvas, Dify New Agent, and NotebookLM's agentic research workspace**. Together they cover task execution, reviewable process changes, and evidence inspection. None repeats the previous study's five selected products.

The design question is specific: how can a claim handler see what needs attention, inspect the work behind it, and correct the process without facing the entire system at once?

## Selection and evidence standard

The user requested awards and public GitHub evidence. Those establish different things. The Webby issuer verifies an award; a public repository verifies inspectable implementation; GitHub-star growth measures attention. Neither an award nor a repository proves successful claim handling. Transfer judgments below are our design inferences.

The UI Skills workflow selected `dammyjay93/interface-design` through `ui-skills-root`. Its useful constraint here is one focal task per view, with controls, evidence, and status arranged by their importance to that task. Humanizer was used for the prose. No model-provider calls, signups, account changes, or product installations were performed.

Eight candidates received a bounded evidence pass:

| Candidate | Verified recognition / public-code evidence | Why selected or set aside |
|---|---|---|
| **OpenHands Agent Canvas** | [Public application repository](https://github.com/OpenHands/OpenHands). OpenHands is fifth in [Runa's annual 2024 ROSS index](https://runacap.com/ross-index/annual-2024/), ranked by absolute GitHub-star growth that year. This historical recognition predates the current Canvas UI. | **Selected:** explicit task activity, reviewable artifacts, and context drawers that do not all remain open. |
| **Dify New Agent** | [Public application repository](https://github.com/langgenius/dify). Dify is third in the same historical [2024 ROSS index](https://runacap.com/ross-index/annual-2024/). This is not a UX award for New Agent. | **Selected:** a concrete distinction between building, applying a draft, testing, publishing, and inspecting affected consumers. |
| **Google NotebookLM** | The award issuer lists it as **Webby Winner, Best AI User Experience, 2026** in the [official category](https://winners.webbyawards.com/winners/ai/ai-features-innovation/best-ai-user-experience). No first-party public UI repository was verified. | **Selected:** research results are reviewable before import; citations lead to their exact source context; outputs have a separate home. Current help pages use the name Gemini Notebook. |
| **Google Opal** | **Webby Winner, Best AI Agent, 2026**, according to the [issuer](https://winners.webbyawards.com/winners/ai/ai-features-innovation/best-ai-agent). [Official interaction guide](https://developers.google.com/opal/overview). No first-party public UI repository verified. | Strong alternative for editable steps, App/Editor separation, and expandable execution details. Set aside because another authoring canvas adds less to this selection than NotebookLM's source-review mechanics. Its documented destructive version restore is unsuitable for CasePath history. |
| **Flowise Agentflow V2** | [Public repository](https://github.com/FlowiseAI/Flowise) and [official V2 interaction guide](https://docs.flowiseai.com/using-flowise/agentflowv2), including execution checkpoints and human-input states. No independent design-award win verified in this search. | Useful process authoring and pause/resume reference, but the node palette and configuration canvas would repeat CasePath's present density if used as its everyday surface. |
| **Sim** | [Public repository](https://github.com/simstudioai/sim) for an agent/workflow builder. Public [runtime configuration](https://github.com/simstudioai/sim/blob/main/apps/sim/.env.example) distinguishes Chat availability from workflow-editor availability. No design-award win verified. | Builder and runtime separation is relevant, but overlaps Dify. Repository access does not mean every hosted feature runs without credentials. |
| **Kortix, formerly Suna** | [Public repository](https://github.com/kortix-ai/suna) describes sessions producing human-reviewed change requests. No independent design-award win verified. | Close task-to-deliverable fit, but current public evidence introduces a larger company-management system; OpenHands offers a more precisely documented disclosure pattern for this bounded redesign. |
| **Pipali by Khoj** | [Public beta repository](https://github.com/khoj-ai/pipali) describes asynchronous work, deliverables, routines, and permission requests. No independent design-award win verified. | Promising task-first reference, but thinner public state documentation and recognition evidence than the selected set. An unrelated Figma plugin also called Khoj was excluded from recognition evidence. |

The ROSS publisher is an investor and its selection concerns open-source startups. These positions are historical popularity measurements, not current product rankings, task-success measurements, or interface awards. Dify's vendor announcement of an AWS Social Impact Partner award was not used as independent design-award evidence. Product Hunt listings, nominations, and voting pages were not promoted into award wins.

## 1. OpenHands: follow the task, then inspect its output

**Observed in primary documentation.** A running conversation has a compact activity chip describing the unresolved action. An inline artifact can open in a Files drawer. The overview is explicitly opened from the header and closes when that drawer opens. Tags and model metadata can remain hidden by default. Failed messages retain a visible recovery action. [Conversation guide](https://docs.openhands.dev/openhands/usage/agent-canvas/conversations).

The September release article supplies published product screens of activity, automations, and artifact/commit review. Its artifact-review sequence is explanation → file → changes → next decision. [Release walkthrough](https://www.openhands.dev/blog/new-in-agent-canvas-august-2026), [published Commits/overview screen](https://www.openhands.dev/assets/notion-blog/new-in-agent-canvas-august-2026/commits-drawer-with-overview.jpg).

**Public-code cross-check.** At repository snapshot `bb4db349c7646c27ff119eef40f1502f735071ee`, the [overview-toggle test source](https://github.com/OpenHands/OpenHands/blob/bb4db349c7646c27ff119eef40f1502f735071ee/__tests__/components/features/conversation/conversation-overview-toggle.test.tsx) explicitly covers opening the overview, closing Files when overview opens, and closing overview when the right drawer opens. We read that source; we did not execute its tests.

**Transfer to CasePath.** Keep the claim's current action and agent state in Overview. Open the process when the handler needs to correct it, and the source when they need to establish a fact. Keep a document preview adjacent to the decision it supports. This reduces the number of competing objects while preserving a stable route back to the claim. That attention benefit is an inference, not a measured result.

**States to retain:** idle, working on a named task, result ready, needs input, failed with retry, and source/output detail open. A hidden technical log may still need a visible failure count. Do not replace a real execution state with a perpetual “thinking” indicator.

**Do not copy:** coding terminology, context-token meters, agent-provider setup, repository controls, or the surrounding automation dashboard into a claim handler's main view. Do not treat an agent's completed task as authorization of a claim outcome.

**Access limit:** this study inspected public docs, published screens, and public source. No authenticated OpenHands run was exercised. The current application supports several backends; backend-dependent behavior must not be generalized to every installation.

## 2. Dify: make the effect of an edit reviewable

**Observed in primary documentation.** New Agent is explicitly beta. Build mode stages configuration changes in a Build draft with Apply/Discard. Preview exercises the end-user experience without changing configuration. Edits can be saved as a draft separately from publishing; version history can restore an earlier version. [Build an Agent](https://docs.dify.ai/en/cloud/use-dify/build/new-agent/build).

The launch article contains concrete screens named Build by Chatting, Preview with Pie Chart, Agent Console, Access Point, Agent Logs, and Last Run. Access Points exposes workflows using the shared agent; logs and node inspection provide deeper execution information in separate surfaces. [Published UI walkthrough, 27 August 2026](https://dify.ai/blog/introducing-new-dify-agent).

**Public-code cross-check.** At `ca27376211cea79670614ffcbb9805d827cd17f3`, [Build draft scenarios](https://github.com/langgenius/dify/blob/ca27376211cea79670614ffcbb9805d827cd17f3/e2e/features/agent-v2/build-draft.feature) specify apply/discard persistence after refresh and protection when leaving Configure. The [publish-impact component](https://github.com/langgenius/dify/blob/ca27376211cea79670614ffcbb9805d827cd17f3/web/features/agent-v2/agent-detail/configure/components/orchestrate/publish-bar/publish-impact-details.tsx) renders a count and links for affected workflows. This is source inspection, not proof that this checkout's tests pass.

**Transfer to CasePath.** Put process authoring in Process. A node edit should present its proposed consequences in one focused review state, then save. Keep “unsaved edit,” “preview checked,” “saved working process,” and “validated reusable version” distinct. Put reusable-fragment scope and version choice next to reuse, not in an always-visible administration panel. The expected benefit is reduced uncertainty about what an action will change.

**States to retain:** untouched, editing, preview loading, proposed impact, save pending, saved, stale/conflicting revision, invalid edit, reusable version selected, and incompatible reuse. Show the affected documents/actions before saving, and preserve the current version until the handler explicitly adopts another one.

**Do not copy:** the full builder toolbox or model configuration. Dify's Build chat is read-only on the configuration side and Apply/Discard clears that conversation; CasePath should preserve its correction history. A polished preview must not conceal insufficient evidence or turn a draft into an approved request.

**Access limit:** no cloud account or sandbox run was used. Public docs specify a beta, Editor access for management, backend/model dependencies, and edition limits for some log archives. Published screenshots may not match every deployment.

## 3. NotebookLM: inspect sources where a claim needs support

**Observed in primary documentation.** Deep Research runs in the background. The user can expand the report and source list, select results, then import. These are separate states. Current documentation also notes that usage limits can cause a partial import. [Source discovery and import](https://support.google.com/gemininotebook/answer/16215270?hl=en).

Citation hover reveals a quotation; selecting it opens the quote in context. Saved notes preserve clickable citations. Current chat help also documents expandable activity, generated files, artifact versions, and Stop controls, while marking those newer agentic capabilities experimental. [Chat and citation interaction](https://support.google.com/gemininotebook/answer/16179559). Reports belong to Studio and have their own generation and review flow. [Report workflow](https://support.google.com/gemininotebook/answer/18323649?hl=en).

**Published screen evidence:** Google's [Deep Research walkthrough, 13 November 2025](https://blog.google/innovation-and-ai/models-and-research/google-labs/notebooklm-deep-research-file-types/) shows the research mode entry and describes work continuing during background research. The [Webby award record](https://winners.webbyawards.com/winners/ai/ai-features-innovation/best-ai-user-experience) concerns Google NotebookLM; it is not a separate endorsement of every newer feature now described under Gemini Notebook. No public wrapper or unofficial GitHub client was treated as the product's source code.

**Transfer to CasePath.** Show a concise source reference beside a factual finding. Open the exact original and passage on demand. Place document requirements and prepared requests in Documents, with their statuses visible before opening details. A handler should be able to inspect a source and return to the same step without losing the pending correction. This preserves the relationship between a claim and its support while avoiding a permanently competing evidence column.

**States to retain:** no source, received but unreviewed, source open, sufficient, insufficient, inaccessible/failed, and stale derived output. A citation is a route to evidence; it does not itself establish that the evidence is sufficient.

**Do not copy:** the persistent three-column Sources/Chat/Studio shell, the broad menu of media formats, or a general chat box as the primary claim workflow. Borrow the retrieval and review transitions. Also do not inherit the documented behavior of discarding unimported research results when exiting; CasePath's retained history is valuable.

**Access limit:** public help and published UI material only. No private notebook or signed-in generation was used. Current help warns of mobile limitations, usage limits, and experimental agentic functions; we make no speed, accuracy, or accessibility claim from these documents.

## Translation into the CasePath implementation

The implementation owner selected the following separation. These are design requirements for this change; completion is established by the local browser/test receipt, not by this research document.

| CasePath surface | Primary job | What belongs on demand | Evidence to inspect during acceptance |
|---|---|---|---|
| Overview | Understand the claim and take the current useful action | Full process editor, detailed facts, complete activity history | Initial view has one clear next action; named live state changes to a truthful result or recovery action. |
| Process | Inspect or correct the working process | Node/connection forms, reusable-fragment controls, historical detail | Select step → edit → impact preview → save; documents and next actions update, and history remains accessible. |
| Documents | Review requirements and prepared outputs | Full source text, individual request editor | Mandatory/conditional/received states remain distinguishable; stale requests cannot appear ready after a process correction. |
| Source detail | Check one original and its supporting passage | Other unrelated sources and graph controls | Open from the relevant fact/requirement, inspect exact source, close and return without losing position or unsaved input. |

Existing causal code already supplies the preview/apply boundary, revision binding, document-review state, and versioned fragment selection. The calmer shell must preserve those semantics. Reducing card borders or hiding panels alone does not complete this task. The decisive comparison is whether a fresh handler can identify the current action, inspect its source, correct the relevant step, understand the impact, and return to daily work with fewer competing controls.

## Evidence receipt

- Retrieval date: **2026-10-02**. Award and leaderboard claims were checked against their issuers; product mechanics against official docs and selected public source files.
- GitHub tree snapshots were retrieved through the public GitHub API. OpenHands: `bb4db349c7646c27ff119eef40f1502f735071ee`; Dify: `ca27376211cea79670614ffcbb9805d827cd17f3`. These identify inspected source, not deployed cloud versions.
- Screens are publisher-provided product material at the URLs above. They are not screenshots of our own completed interaction. Some direct image requests returned unsupported-content errors; the containing documentation remained readable.
- The implementation owner visually inspected the publisher's OpenHands drawer, Dify Build Apply/Discard screen, and NotebookLM Deep Research header through ego-browser; this is published reference evidence, not evidence of a run we performed in those products.
- No commercial product was run, no accessibility audit was performed, and no measured comparative usability claim is made. No raw provider calls or external writes occurred.
- Scope of this research write: this document only. CasePath's runtime, visual acceptance, persistence, and recovery verification remain the implementation owner's evidence.
