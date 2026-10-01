# CasePath agentic UX benchmarks

Research date: 1 October 2026. Scope: public product documentation, documentation screenshots and references, independent reviews, design publications, award records, and curated SaaS references. Three public documentation pages were opened in Ego Browser and their embedded product-state examples were captured and visually inspected. No authenticated customer workspace was exercised. No signup, purchase, customer message, or external mutation was performed. Humanizer was applied in embedded mode.

## Decision

Use five complementary benchmarks: **Linear, n8n, Fin/Intercom, Replit Agent, and Notion**. Together they provide useful patterns for accountable delegation, executable dependencies, precise human review, visible change/recovery, and durable shared knowledge. This is a selection for CasePath's job, not a ranking of the five best products overall.

The strongest resulting interaction is a claim workspace that shows the applicable process, work underway, evidence, and the next decision. Selecting a process step opens a small operational inspector. Editing that step produces a concrete impact preview, updates its dependent requirements, and records the change. These are design proposals inferred from the benchmarks; no source establishes that this combination will improve claim handling without user testing.

## Evidence standard and source coverage

- **Award records:** Webby records establish exactly which Notion entry won which category. The 2022 productivity award predates its current agents. A separate 2025 AI Assistant award is credited to BUCK; it is not evidence that current Custom Agents have been evaluated. The art-direction nomination explicitly judges visual style and receives no weight as workflow evidence. [2022 productivity award](https://winners.webbyawards.com/2022/apps-and-software/software-services-platforms/productivity-collaboration/208566/notion), [2025 AI award](https://winners.webbyawards.com/2025/apps-software/app-features/best-use-of-ai-machine-learning/332061/notion-ai-assistant), [art-direction scope](https://winners.webbyawards.com/2025/ai-immersive-games/ai-apps-experiences-features/best-art-direction/332062/notion-ai-assistant).
- **Design awards beyond familiar SaaS:** iF records Philips' clinical documentation assistant under Health/Wellness UX. UX Design Awards' 2025 yearbook indexes Seek AI and discusses combining conversation with structured data work. These are useful discovery sources, with insufficient public execution-state evidence for the final five. The full yearbook exceeded the web reader's size limit; only indexed excerpts were inspected. [Philips entry](https://ifdesign.com/en/winner-ranking/project/philips-precision-treatment-assistant/679529), [UX Design Awards yearbook](https://ux-design-awards.com/media/pages/events-media/ux-design-awards-yearbook-2025/f1108abc71-1758553537/digital_yearbook_2025.pdf).
- **Independent evaluation:** NN/g tested AI prototyping tools using common scenarios and published its methodology and outputs. It observed that detailed inputs improve fidelity but generated designs still miss hierarchy, contrast and spacing. This supports reviewing actual artifacts, not accepting a generated surface as finished. [Methodology](https://www.nngroup.com/articles/testing-ai-methodology/), [results](https://www.nngroup.com/articles/ai-prototyping/).
- **Editorial product reviews:** TechRadar's Replit review describes an actual test build; its older Intercom and Airtable reviews assess workflow and navigation while documenting limitations. These are editorial judgments, not controlled usability experiments. Affiliate links are disclosed. [Replit test](https://www.techradar.com/pro/software-services/replit-no-code-review), [Intercom review](https://www.techradar.com/pro/intercom-review), [Airtable review](https://www.techradar.com/reviews/airtable-review).
- **Customer evidence:** Capterra's n8n reviews and G2's Fin summaries add reports from users about maintenance, setup and handoff. Reviewer selection and aggregation limit generalization. G2's Fin evaluation page explicitly labels task evaluation unavailable and separates vendor performance claims from buyer reviews; no vendor resolution-rate claim is treated as independent proof. [n8n reviews](https://www.capterra.com/p/198028/n8n-io/reviews/), [G2 Fin evidence boundary](https://ai.g2.com/evaluations/categories/customer-experience/fin-intercom).
- **Design publications and curated galleries:** First Round and Lenny interview Linear's founder about product craft; they establish design intent and professional interest, not independent task success. SaaSFrame's release commentary gives concrete in-context review patterns. Awwwards' experimental gallery was screened but did not establish operational workflow quality for a final candidate. [First Round](https://review.firstround.com/podcast/inside-linear-why-craft-and-focus-still-win-in-product-building/), [Lenny](https://www.lennysnewsletter.com/p/inside-linear-building-with-taste), [SaaSFrame](https://www.saasframe.io/releases), [Awwwards gallery](https://www.awwwards.com/websites/experimental/).

## Broad candidate ledger

Twelve products were considered before narrowing. “Considered” means public evidence screened; only the final five received the deeper state analysis below.

| Product | Evidence and useful interaction | Selection decision |
|---|---|---|
| Linear | Design-publication interviews, SaaSFrame curation, and current delegation docs. Work remains in the owner's queue while an agent acts. | Select for calm work organization and accountability. |
| n8n | Capterra users describe being able to follow data and connections; official docs specify selective approvals and execution replay. | Select for inspectable execution and modular process work. |
| Fin/Intercom | TechRadar praises AI functionality and integrations but notes price/learning burden; G2 users report useful handoffs and occasional loops. Official procedure docs expose lifecycle and review states. | Select for procedural autonomy, exception handling, and version scope. |
| Replit Agent | NN/g includes it in a comparable task evaluation; TechRadar tests prompt-to-working-app generation. Current docs show plan approval and checkpoints. | Select for intermediate artifacts, progress and recoverable change. |
| Notion | Verified Webby productivity recognition plus current Agent/Custom Agent docs. Editable persistent instructions and per-run activity offer a reference for maintained knowledge. | Select for visible accumulation and editable shared structures. |
| NotebookLM | A Tom's Guide workflow comparison praises source-grounded analysis. | Useful reference for evidence proximity; overlaps with provenance lessons and contributes less to executable state. [Review](https://www.tomsguide.com/ai/i-finally-figured-out-when-to-use-gemini-notebooks-vs-notebooklm-heres-the-winning-workflow) |
| Airtable | TechRadar describes multiple views, easy navigation for narrow tasks, and excessive horizontal scrolling on mobile. | Useful relational views; n8n better exposes execution dependencies for this study. [Review](https://www.techradar.com/reviews/airtable-review) |
| Zapier | TechRadar describes approachable automation and a template library. | Strong onboarding candidate; overlaps with n8n, which contributes more directly to graph inspection. [Overview](https://www.techradar.com/computing/artificial-intelligence/what-is-zapier-ai-everything-you-need-to-know-about-the-ai-automation-tool) |
| Seek AI | UX Design Awards yearbook describes natural-language data questions within structured workflows. | Promising specialist; public state-level evidence was too thin for deep selection. [Yearbook](https://ux-design-awards.com/media/pages/events-media/ux-design-awards-yearbook-2025/f1108abc71-1758553537/digital_yearbook_2025.pdf) |
| Philips Precision Treatment Assistant | iF entry describes draft clinical notes that professionals edit and validate before record integration. | High transfer potential for consequential review, but entry text alone cannot verify error/recovery flows. [Award](https://ifdesign.com/en/winner-ranking/project/philips-precision-treatment-assistant/679529) |
| Figma Make | Included in NN/g's tested interactive-prototype group. | Direct manipulation is useful; executable business-process state is outside the evaluated use case. [Methodology](https://www.nngroup.com/articles/testing-ai-methodology/) |
| Lovable | NN/g shows a close design translation from a Figma reference while noting general generated-detail weaknesses. | Useful first-artifact speed; substantially overlaps with Replit for the current purpose. [Results](https://www.nngroup.com/articles/ai-prototyping/) |

Selection favored complementary coverage of the user's requirements, current inspectable documentation, and concrete recovery behavior. Popularity, visual polish, awards outside workflow categories, and vendor success-rate claims did not decide the final five.

## 1. Linear: delegation inside a stable work system

**Documented mechanics.** Linear assigns an issue to a person and delegates work to an agent while preserving the human's ownership. Delegated issues remain in My Issues; filters separate assignee and agent, and the Activity feed records assignment changes. Agents are subject to team access. [Assignment and delegation](https://linear.app/docs/assigning-issues). Coding sessions stay tied to the issue, return a draft PR and diff, and notify the user when input is needed. [Coding sessions](https://linear.app/docs/coding-sessions).

**Recognition and its limits.** First Round's interview focuses on opinionated workflows and the simplicity/flexibility tradeoff. SaaSFrame specifically praises contextual artifact previews and persistent review access. These are more relevant than its marketing-site curation. [Interview](https://review.firstround.com/podcast/inside-linear-why-craft-and-focus-still-win-in-product-building/), [release analysis](https://www.saasframe.io/releases).

**Why it works / expected psychological effect.** The user has one place to return to and can delegate without losing responsibility. Stable positions for controls reduce search; visible ownership supports control and continuity. These effects are design hypotheses for CasePath, not measured results from this study.

**CasePath transfer.** Keep claim owner, current state and one next action at the top. Put agent activity within the claim. Use a compact “Needs your review” queue for unresolved nodes and relationships. Work should become navigable through durable claim/process objects, so the chat transcript is optional context.

**Do not copy.** Software issue jargon, tiny dense typography, shortcut-dependent discoverability, or a prominent PR/diff metaphor. A claim handler should read “What changes” and “Apply to this claim.”

**States and visual references.** The official assignment page includes an assignment/delegation screenshot and filtered-list screenshot. The 2026 design refresh documents clearer headers, calmer sidebars and predictable action placement. It is a source for hierarchy, not a mandate for a dark theme. [Refresh](https://linear.app/now/behind-the-latest-design-refresh). Authenticated onboarding, motion, keyboard behavior and error recovery were not exercised.

## 2. n8n: execution can be inspected at the point that matters

**Documented mechanics.** A tool can require approval while others proceed. The workflow pauses, presents the exact proposed tool/input, and either executes after approval or cancels after denial. This creates a local review boundary. [Human review](https://docs.n8n.io/build/integrate-ai/ai-examples/human-in-the-loop-for-tools.md). Past execution data can be opened in the editor: failed runs offer “Debug in editor,” successful ones “Copy to editor,” and the original input can be pinned. [Execution debugging](https://docs.n8n.io/build/understand-workflows/understand-executions/debug-executions.md).

**Recognition and its limits.** Capterra reviewers praise visible connections, inspectable data flow and the ability to revisit a workflow. They also describe maintenance and debugging work. TechRadar's comparison observes that constructing such workflows can be demanding. This supports borrowing inspectability while reducing authoring burden. [User reviews](https://www.capterra.com/p/198028/n8n-io/reviews/), [comparison](https://www.techradar.com/pro/n8n-vs-openclaw-what-are-the-differences-and-where-should-you-use-either-of-them).

**Why it works / expected psychological effect.** A selected step gives a concrete explanation of what it received and produced. Local review preserves momentum elsewhere; retained inputs make a failure reproducible. The intended effects are comprehension, control and repair confidence.

**CasePath transfer.** Each process node needs a readable condition, prerequisites, evidence, validation state and required documents. A document row should link back to every active node requiring it. A changed prerequisite should identify downstream state that needs recomputation. Show “Waiting for repair estimate” and the specific blocking relationship, not a generic failure badge. Group reusable fragments behind meaningful names, with details on demand.

**Do not copy.** A blank infinite canvas, connector configuration, JSON inspectors as the default, or requiring a handler to wire an automation before seeing value. The operational path should open preconstructed; technical graph details stay available behind ordinary controls.

**States and access.** Approve, deny, paused, successful and failed execution are documented. Subworkflow and “dirty node” pages were discovered in the official sitemap but their bodies could not be retrieved; detailed stale-output UI claims are therefore excluded. No n8n execution was run. [Official documentation index](https://docs.n8n.io/sitemap.md).

## 3. Fin/Intercom: a procedure has a lifecycle and a clear exception path

**Documented mechanics.** Fin separates procedure changes into unsaved, saved draft, and live states; only the live version affects conversations. [Version lifecycle](https://www.intercom.com/help/en/articles/14324571-manage-procedure-versions-and-publishing). The procedure editor distinguishes Preview from Simulations. Its documentation warns that previewing a live procedure can expose messages to customers, while simulations have no customer-facing output. [Building procedures](https://www.intercom.com/help/en/articles/13449439-building-fin-procedures). A human-review step pauses, sends context for a decision, and resumes when a response returns; it also has a timeout. [Human review](https://fin.ai/help/en/articles/16049727-human-in-the-loop-approvals-for-fin-procedures).

**Recognition and its limits.** TechRadar's 2024 review praises AI functionality and integrations while reporting learning burden. G2's review analysis emphasizes context-preserving handoff but also repeated answers and tuning requirements. The older editorial review does not validate the 2026 procedure feature set. [Review](https://www.techradar.com/pro/intercom-review), [user themes](https://learn.g2.com/best-conversational-support-platforms-for-customer-service).

**Why it works / expected psychological effect.** Draft/live separation makes exploration safe to reason about. A waiting state tells the handler who must act and what happens next. Users should feel that the system can recognize a boundary and preserve context through it.

**CasePath transfer.** Split a correction to this claim from a proposal to update a reusable process definition. Show affected claims/fragments before a shared update. Preserve the previous definition for existing instances. A blocked node should expose its missing decision and whether other work can proceed. Review should approve the specific condition or relation, not silently validate an entire inferred graph.

**Do not copy.** Conversational response volume as a success metric, automatic acceptance of an AI simulation's pass/fail, or Fin's exact sequential execution limitations. Claim-process correctness requires deterministic invariants and appropriate human review, even when an agent proposes the structure.

**States and access.** Documented: draft/live/paused lifecycle; normal and exceptional paths; waiting/approval/denial/timeout; simulation pass/fail; rollback. Help articles provide procedure-editor references. No live customer conversation or authenticated editor was opened.

## 4. Replit Agent: proposed work, visible artifacts, and scoped recovery

**Documented mechanics.** Plan Mode generates a task plan before modifying code or data. The user can revise, cancel, build here, or build in the background; background changes wait for review/application by default. [Plan Mode](https://docs.replit.com/features/agent/plan-mode). Checkpoints name logical milestones and expose change scope and history. Current rollback documentation states that database restoration is optional for development and that production databases require a separate restore path. [Checkpoints](https://docs.replit.com/features/version-control/checkpoints-and-rollbacks).

**Recognition and its limits.** TechRadar describes generating and then inspecting a small application. NN/g includes Replit in a published evaluation with shared prompts. Neither establishes safety for claim operations. The widely reported production-database incident is an explicit counterexample to trusting an agent's confident narrative. [Test review](https://www.techradar.com/pro/software-services/replit-no-code-review), [NN/g results](https://www.nngroup.com/articles/ai-prototyping/), [incident reporting](https://www.tomshardware.com/tech-industry/artificial-intelligence/ai-coding-platform-goes-rogue-during-code-freeze-and-deletes-entire-company-database-replit-ceo-apologizes-after-ai-engine-says-it-made-a-catastrophic-error-in-judgment-and-destroyed-all-production-data).

**Why it works / expected psychological effect.** A visible plan establishes a boundary; an intermediate artifact lets the user judge progress; named checkpoints provide a route back. Together they can reduce the fear of correcting generated work.

**CasePath transfer.** Before a consequential edit, show the concrete effect set: nodes activated/deactivated, requirements added/removed, completed steps reopened, next action changed. After applying it, leave a compact persistent change receipt and a route to inspect the previous state. Keep external actions separate: reverting a graph cannot unsend a document request.

**Do not copy.** Terminal-style streaming, artificial typing or fabricated progress, all-or-nothing regeneration, or “undo everything” promises. The graph evaluator should generate the preview and commit from the same proposal/version, preventing a preview that differs from the applied change.

**States and access.** Public docs contain plan/revise/build and checkpoint/rollback screenshot references. They document historical review and restoration scope; actual rollback, notifications and motion were not tested. Direct web-reader access to one checkpoint asset returned 403. The public Plan Mode page rendered successfully in Ego Browser, and its task-plan example was captured and inspected.

## 5. Notion: durable, editable knowledge with separate configuration history

**Documented mechanics.** Notion Agent can use page or selected-block context. Its instruction page is editable and can accumulate preferences; the documentation explicitly warns that other editors can change behavior by changing that page. [Agent](https://www.notion.com/help/notion-agent). Custom Agents expose Chat, Activity and Settings; logs include triggers, actions and failures, while configuration version history shows who changed what and can restore earlier versions. Access is explicitly scoped. [Custom Agents](https://www.notion.com/help/custom-agents).

**Recognition and its limits.** Notion's verified productivity Webby supports inclusion as an information-work benchmark. The BUCK AI award and nomination categories concern a separate entry and must not be used to imply validated current autonomy. [Productivity award](https://winners.webbyawards.com/2022/apps-and-software/software-services-platforms/productivity-collaboration/208566/notion), [AI entry](https://winners.webbyawards.com/2025/apps-software/app-features/best-use-of-ai-machine-learning/332061/notion-ai-assistant).

**Why it works / expected psychological effect.** Knowledge survives the conversation and can be inspected where work happens. A bounded edit makes correction feel possible. An activity log can answer what happened while the user was absent.

**CasePath transfer.** Make reusable process fragments durable objects with evidence, version, applicability and validation scope. Show a small “Process improved” receipt explaining what was learned and whether it is used only here, proposed for reuse, or adopted in a new version. “Used in this claim” must link to the exact definition version. Let users inspect the distinction between current organizational process and the instance's frozen starting version.

**Do not copy.** A freely edited shared page whose changes silently alter every past claim, a second “expert knowledge” silo, agent personalities, or vague memory claims. The knowledge object remains the process and its causal relationships.

**States and access.** The docs cover creation from templates, natural-language setup, scoped access, activity failures, edit/publish and version restore. Current Custom Agents require eligible plans; no plan was purchased and no authenticated run was tested. Public editor illustrations are references only.

## Browser inspection receipts

Captured and visually inspected on 1 October 2026 in Ego Browser, using the existing CasePath task space 47 and a separate temporary documentation tab. These images capture published product examples inside official documentation. They do not establish authenticated execution or independent task success. The three screenshots are local evidence files; the source links remain usable outside this checkout.

| Capture | Concrete visual observation | Source and local receipt |
|---|---|---|
| Linear delegation | An in-progress issue puts its human owner and delegated agent together in the properties area; linked work appears above the properties. | [Official page](https://linear.app/docs/assigning-issues); `references/linear-delegation.png` |
| Replit plan | A bounded task-plan card shows a short intent summary, a View control, Build here as the primary action, and Revise/Cancel beneath it. Build in background is a distinct choice. | [Official task-planning section](https://docs.replit.com/features/agent/plan-mode#task-planning); `references/replit-plan.png` |
| Fin review step | A procedural review step exposes response collection and wait duration. Its settings panel keeps connection setup, requested response fields and timeout together beside the step. | [Official step configuration](https://fin.ai/help/en/articles/16049727-human-in-the-loop-approvals-for-fin-procedures#h_ac42a18a46); `references/fin-review-step.png` |

The Fin page initially timed out waiting for the load event but had committed successfully; inspecting the same page recovered its rendered content. Optional cookies were rejected. No product action in an authenticated application was executed. Linear's snapshot is dark-themed; that color scheme is not itself a recommendation for CasePath.

Screenshot SHA-256 receipts:

- `fin-review-step.png`: `44c60b9500816883dd334fc5ec0dfba0f74d331d814240c4f5340bd95fc769ba`
- `linear-delegation.png`: `1cf2e1476f47a0e0a19f82cffc4f4c348b434858a9fdf7bdcacfa21ff7056413`
- `replit-plan.png`: `4027767465f607335f720facf5774ec337b4c279c57c998d20a5c13bbcb8db68`

## Translation into a concrete CasePath flow

1. **Start with a useful claim.** Provide a clearly labeled sample claim alongside entering a real claim. Show the case summary first, then reveal the reconstructed process and derived requirements as actual work completes. Each visible status must correspond to a real event or truthful local computation. Never delay an immediate computation to imitate autonomous work.
2. **Show the applicable path.** Display meaningful procedural steps and labeled dependencies. Use textual state labels plus restrained color. The main view should answer “What can happen next?” while the inspector answers “Why?”
3. **Derive the document view.** Each requirement names its requiring node/condition. Deduplicate a document shared by multiple active nodes but retain all reasons. Show inactive requirements as no longer required in the change receipt; avoid silently removing evidence of a prior request.
4. **Correct one thing.** Selecting a node reveals its condition, evidence and local validation. The edit action produces an impact preview before commit. Apply and cancel are visible. The preview includes unresolved conditions and invalidated completed work, not just counts.
5. **Return a receipt.** After applying, show “Changed condition; 2 steps affected; 1 document no longer required; next action updated,” with inspectable items. Preserve who/what changed it and why. This sentence is an illustrative format, not a claim about a current case.
6. **Accumulate reusable process knowledge.** Offer a scoped proposal to update a process fragment. Record which claim supported it and which reviewer validated which element. Existing historical claim instances remain tied to their versions until an explicit migration with impact review.
7. **Return the user to work.** Keep history and system detail behind the inspector/activity drawer. Default to the case, the active process and the next useful action.

## State coverage to implement and verify

| State | User should see | Available action |
|---|---|---|
| Empty | Value demonstrated by one labeled sample and a short intake | Open sample / add claim |
| Working | Current real operation, accumulated artifacts, elapsed time if meaningful | Inspect completed work / cancel supported operation |
| Ready | Current applicable path and next action | Work on the recommended item |
| Needs review | Exact uncertain node/edge and evidence boundary | Validate / correct / dispute that element |
| Waiting | Missing prerequisite, responsible party and downstream effects | Supply evidence / request it / review condition |
| Failed | Failed operation, retained prior state and recoverable input | Retry safely / edit input |
| Edit preview | Before/after and affected elements | Apply / cancel |
| Applied | Updated graph, requirements and next action plus change receipt | Inspect history / scoped undo where supported |
| Shared update proposed | New definition, evidence and scope of reuse | Approve new version / retain local correction |
| Conflict | Competing rules or versions and affected claims | Resolve with evidence; preserve both histories |

This study establishes documented interaction references and a design rationale. Authenticated usability, actual notification timing, animation quality, visual accessibility in each benchmark and customer willingness to pay remain untested. CasePath implementation should be judged through its own scenario tests and real user observation, particularly whether a handler can explain a document's requirement and predict the consequences of a correction.
