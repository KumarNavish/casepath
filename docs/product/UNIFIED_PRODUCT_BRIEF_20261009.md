User acceptance brief, adopted 9 October 2026.

CasePath — One Unified, Autonomous, Motion-Native Product
1. Product objective
Consolidate the existing CasePath work into one coherent website and one functioning product that brings together the complete synthetic claim collection, autonomous claim handling, evidence-driven process graphs, process-derived document checklists, and a deeply organized, evolving knowledge base.
This is neither a dataset-import task nor another standalone demonstration. It is a product-consolidation and experience-redesign task.
The website may contain distinct internal pages, but they must share a consistent product shell, navigation, object identities, execution history, and visual language. A separate page must not mean a separate application or a different version of the same claim.
The intended experience is:
Explore the claim collection → Watch or inspect autonomous handling → Follow evidence into process decisions and document requirements → Understand the resulting actions → Explore the reusable knowledge behind them → Move naturally to related cases.
The system should support both a compelling automated client demonstration and deliberate exploration of the complete product. Neither should depend on navigating to another website or manually operating the agent’s intermediate steps.
2. Make the original 150-claim collection a first-class part of CasePath
Preserve the actual dataset
Use the existing corpus rather than replacing it with simplified examples. The reviewed inventory reports:
Corpus dimension
Reported inventory
Original claims and customer messages
150 unique records
Defect/mold/heating
50 claims
Lease termination
50 claims
Rent increase
50 claims
Scenario families
28
Languages
75 English; 75 Swiss Standard German
Original attachments
57: 47 PDFs and 10 JPEGs

These are findings reported by the supplied review, not new verification performed for this proposal. Untitled document (1)
Preserve every original claim’s identity, message, attachment relationships, and source bytes. Do not manufacture attachments for cases that have none, rewrite messages for demonstration convenience, or silently substitute extracted text for an original document.
Design an intelligent collection—not a raw inventory
The complete collection should be immediately discoverable within CasePath and organized around meaningful scope, domain, and case characteristics.
Use a clear domain-level overview, useful search, concise case previews, and contextual refinement. Make the diversity of the collection understandable without forcing users through nested dropdowns, configuration panels, or an undifferentiated wall of cards.
Users should be able to open any case and inspect its original intake and attachments, then see whatever processing state genuinely exists. Related cases and relevant reusable knowledge should be accessible without losing context.
All 150 cases must be available; they must not all be presented as already investigated. A case that has not run should show its intake and an honest unprocessed state—not an invented substantive graph, checklist, or outcome.
Keep browsing metadata separate from decision evidence
Domain and scenario-family metadata may support collection navigation and representative demo selection. It must not become a shortcut that supplies the agent with the expected process or answer.
Keep reference answers, evaluator labels, protected split information, and authored study graphs outside the operational evidence available to the agent. The review identifies this separation as an existing product boundary that must be preserved. Untitled document (1)
3. Build a representative, genuinely automated nine-case demonstration
Select nine original records
Feature exactly nine claims: three from each of the three tenancy domains. These must be selections of the original records, not new copies or substitute fictional packets. Nine cases demonstrate breadth across the three domains; they do not establish coverage of all 28 scenario families. Untitled document (1)
Choose the nine through source inspection, seeking meaningful variation in circumstances, decision branches, document availability, uncertainty, and handling limits. Cover both languages across the selection.
Include a genuine missing-evidence situation and a case that exposes partial or unsupported source interpretation. Select these from the actual inputs; do not invent missing documents or extraction failures for dramatic effect. Do not select only cases expected to produce smooth success.
Record the selected original IDs and a concise, source-based explanation of their representativeness. This selection record should make coverage inspectable without burdening the main demonstration interface.
Make the demo a mode of the same product
A featured case must open the same underlying record, original sources, and accepted execution history that users encounter in the full collection.
The demo must not have its own process generator, checklist logic, knowledge store, fabricated results, or special backend path.
Starting the automated presentation should let the viewer follow a purposefully paced sequence of meaningful work without repeatedly clicking to advance the agents. Optional inspection should deepen understanding—not become a prerequisite for progress.
Use clearly distinguished modes:
Live execution: The existing engine performs authorized work, and the interface reflects its actual events.
Verified replay: The interface presents a previously recorded, source-bound execution without repeating model calls, external actions, or knowledge publication.
Never silently substitute one for the other. Replay is a way to inspect and demonstrate real recorded work, not permission to animate an authored story.
Require substantive behavior, not nine nominal “runs”
The demonstration must reveal meaningful differences in evidence handling, process branches, document requirements, or justified outcomes across the three domains.
A legitimate evidence or authority limitation may lead to a justified deferral. However, nine imported records—or nine runs that stop before meaningful investigation because inference is unavailable—do not satisfy the demonstration objective.
Operational honesty and substantive autonomous behavior are both required. Neither substitutes for the other.
4. Make the graph, checklist, evidence, and actions function as one system
The core mechanism must operate through shared state:
Source evidence → Established or unresolved facts → Process decisions and active branches → Evidence obligations → Document requirements → Authorized actions and observed outcomes.
The process graph must actually determine the checklist and applicable next actions. It must not be a visual illustration attached after an independently generated answer.
Selecting a document requirement should reveal the process decision and fact that justify it. Selecting a process node should reveal its relevant evidence, unresolved questions, obligations, and dependencies. Changes to evidence or branch conditions should propagate consistently into the affected requirements and actions.
Distinguish document availability from document understanding
Throughout the product, distinguish:
File received → Content extracted, fully or partially → Content interpreted → Evidence sufficient for a particular decision.
A supplied but unread document is not automatically a missing customer document. A successful preview does not prove that the agent understood its contents. Conversely, possession of a document does not establish that it answers the relevant question.
The reviewed implementation preserves JPEGs without interpreting them and marks some PDF extraction as incomplete. These are capability gaps to represent accurately and improve where existing authorized capabilities permit—not evidence to silently treat as understood. Untitled document (1)
Keep operational status and presentation mode distinct
A case’s execution status—unprocessed, running, completed, deferred, or failed—is different from whether the user is viewing live activity, saved results, or replay.
Likewise, completing an investigation is not the same as resolving or settling a claim.
Present these distinctions concisely and consistently. Do not obscure them with repeated warnings, competing badges, or explanatory paragraphs.
Agents should progress autonomously within their established capabilities and authority. Do not introduce routine human approval steps into the demonstrated workflow. When the system cannot proceed, preserve the actual state and reason rather than implying successful completion.
5. Make organizational knowledge a deeply structured, visible product capability
The knowledge base must be more than a list of previous cases, generated summaries, or stored documents.
It should organize reusable operational knowledge around:
Scope and applicability → Reusable processes → Decisions and branch conditions → Required facts → Evidence and document requirements → Actions, exceptions, and limits.
Each reusable entry should retain its supporting sources, applicable conditions, qualification state, version history, and relationships to contributing and consuming cases.
The corpus’s scenario-family labels may help users browse, but must not automatically become authoritative process definitions.
Show genuine qualification, refinement, and reuse
The product should make it possible to follow knowledge from a case into a reusable entry and from that entry into a compatible subsequent original case.
Candidate knowledge must remain distinguishable from knowledge that has passed the system’s automated qualification checks. Reuse should depend on supported applicability—not merely similarity of category labels.
Create a new version when the reusable definition materially changes. When a case confirms an unchanged definition, record the additional supporting relationship without manufacturing a new version to make the interface appear active. This follows the review’s distinction between meaningful knowledge change and redundant publication. Untitled document (1)
At least one demonstrated cross-case sequence should expose actual qualified reuse, with inspectable links in both directions.
Successful retrieval or reuse must not, by itself, be described as measured improvement. The interface should show what knowledge was applied and what it influenced; stronger performance claims require separate evidence.
6. Apply one motion-native interaction system across the entire product
Visual and experiential quality is a core deliverable—not a finishing pass after engineering acceptance.
The collection, claim workspace, evidence viewer, graph, checklist, demonstration, and knowledge base should feel like different perspectives on one intelligent environment.
Use motion to explain relationships
Create a consistent visual language for evidence arriving, facts being established, branches activating, obligations becoming relevant, actions completing, and knowledge being qualified or reused.
Preserve spatial continuity so viewers can follow what changed and why. Let the relevant objects carry the explanation rather than adding paragraphs around them.
Motion must correspond to real events and dependencies. Completed work should settle into a clear, inspectable state rather than continue pulsing as though it were active.
Do not imply parallel execution that does not exist. The review reports one current worker; visual representations of roles or handoffs must not misrepresent that as concurrent workers. Untitled document (1)
Simplify without concealing substance
Use precise typography, clear hierarchy, restrained surfaces, readable source presentation, and contextual disclosure.
Avoid the recurring regressions:
Turning every requirement into another card, panel, dropdown, or permanent status indicator.
Adding explanatory copy where a better interaction would communicate the relationship directly.
Treating animated loading indicators, generic entrances, or cosmetic styling changes as an agent-native redesign.
Distinct internal pages are appropriate. Do not force the whole product onto one overloaded canvas in the name of unification.
The same quality must hold across all three domains, large collections, long-running work, unprocessed cases, incomplete evidence, and failures—not only a selected flagship screen. Keyboard access, readable contrast, and reduced-motion behavior must preserve the same understanding.
The target is a refined, distinctive product whose intelligence becomes apparent through its behavior—not an ordinary dashboard with agent terminology.
7. Integrate around canonical identity, accepted history, and bounded execution
Preserve one authoritative record and history
Every original case needs a stable canonical identity. Each execution may have its own run identity, but it must remain bound to the original case, its sources, and its accepted history.
Bind or migrate compatible existing records without rewriting historical events. Do not merge unrelated legacy demonstration packets into original corpus cases merely to make the inventory appear unified.
Original files, extracted text, replay records, and cached summaries are legitimate separate representations when their inputs and revisions are explicit. The requirement is consistent identity and state, not “only one representation of the data.” Untitled document (1)
Collection summaries may use efficient projections rather than reconstructing every complete history on every page load. Measure performance and stale-state behavior; do not introduce a second source of truth.
Preserve execution and cost boundaries
Browsing, previewing, navigating, refreshing, and viewing replay must not initiate fresh inference or repeat actions.
Before fresh demonstration execution, inspect existing usage, reservations, configured capabilities, and authorized allowance. Preserve the spending ledger and prior reservations. Do not add spending, reset counters, or silently change providers to bypass an unavailable allowance.
The review’s nominal estimate of 18 first-pass model calls for nine fresh runs excludes retries and evidence updates; it is not proof of available capacity or a cost authorization. Untitled document (1)
Where live execution remains unavailable, report the precise limitation. A valid existing replay can support presentation, but it must not conceal that limitation or be counted as a new live run.
8. Implement and verify through four integrated milestones
Milestone 1 — Canonical collection and product foundation.
Expose all 150 original records and their source bindings in the unified product without requiring inference. Establish the shared navigation and visual language immediately, rather than postponing design until after import.
Milestone 2 — Shared execution and connected workspaces.
Connect original cases to the existing engine and accepted history. Verify that evidence, graphs, checklists, actions, and knowledge references stay consistent through navigation, new evidence, reloads, retries, and replay.
Milestone 3 — Representative autonomous demonstration and knowledge reuse.
Execute within authorized resources or verify existing histories for the nine selected cases. Inspect meaningful differences across domains, document timing, justified deferrals, and genuine cross-case knowledge qualification and reuse.
Milestone 4 — Product-wide experience and release verification.
Inspect the actual rendered website across desktop and mobile, including collection browsing, original document viewing, unprocessed states, ongoing execution, failures, saved results, and replay. Verify persistent-state readback and the intended source version in the authorized release environment.
At every milestone, inspect the actual interaction experience—not only tests, schemas, or screenshots. Preserve observed failures and unresolved limitations alongside successful checks.
9. Final acceptance standard
Requirement
Completion evidence
One CasePath
Collection, demonstrations, claim handling, evidence, and knowledge are internal parts of the same product and resolve to shared records and history.
Complete original collection
All 150 original claims are accessible; messages and all 57 attachments retain correct identities, relationships, and bytes.
Representative automated demo
Nine original cases, three per domain, have inspectable source-bound histories and demonstrate substantive behavior across the three domains.
Actual process-to-document causality
Requirements trace to active process decisions and evidence obligations; relevant state changes propagate consistently.
Organized, reusable knowledge
Qualified entries expose scope, sources, versions, and actual contributing/consuming case relationships, including demonstrated compatible reuse.
Truthful autonomy
No routine manual orchestration; live work, replay, unresolved evidence, capability limits, and deferrals are accurately represented.
Exceptional product-wide UX
Direct browser inspection demonstrates coherent navigation, clear hierarchy, readable sources, and meaningful event-linked motion across major pages and states.
Reliable persistence and execution
Navigation, reload, retry, and replay preserve state without duplicating inference, actions, publication, or spending.

Technical acceptance and experiential acceptance are both mandatory. A beautiful scripted presentation is insufficient. So is a technically consistent but ordinary dataset browser.
The finished result should let a client explore the breadth of the original collection, observe autonomous handling, understand why evidence creates particular process and document requirements, and see how qualified knowledge connects cases—all within one coherent experience.
Success is one definitive CasePath product that brings the existing work together without weakening its functionality, hiding its limitations, or compromising the agent-native experience.


