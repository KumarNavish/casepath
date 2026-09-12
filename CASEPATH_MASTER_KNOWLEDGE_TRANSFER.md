# CasePath Master Knowledge Transfer

> **Standalone repository note (2026-09-12):** This is a retained historical
> record. Current work belongs in <https://github.com/KumarNavish/casepath> on
> `main`. Old repository, branch, hosted-service, research, and provider
> instructions below are provenance, not current operating guidance. Start
> with `README.md`, `AGENTS.md`, and `docs/PRO_HANDOFF.md`.

> **Purpose:** operational memory for the next AI agent, researcher, engineer, or product designer.
> **Audience:** a capable collaborator with no prior conversation context.
> **Product code baseline inspected:** `KumarNavish/KumarNavish.github.io` at product commit `a867bb506d8e3f790806fc21f2a24a011c1cd0bc`.
> **Public product inspected:** <https://casepath-swiss-claim-lab.onrender.com/>
> **Public API inspected:** <https://casepath-agentic-api.onrender.com/>
> **Canonical browser evidence inspected:** <https://casepath-guided-canonical-qa.onrender.com/>
> **Reconstruction date:** 11 August 2026.

---

## Read this first

CasePath has accumulated several generations of code, benchmarks, papers, release branches, prototypes, and product redesigns. They are related, but they are **not one synchronized system**.

The fastest way for a new collaborator to waste time is to assume that:

- the 150-claim bilingual corpus is the data used by the deployed product;
- the hardened 48-journey defects benchmark is committed in the current default branch;
- the public v20 experience runs LangChain or Nemotron;
- the public Swiss-law component is a live retrieval system;
- the public expert correction performs a fresh regression experiment before promotion;
- the current API has durable persistence;
- or every version marker in the repository agrees.

None of those statements is currently true.

The current project must be understood as three principal layers:

| Layer | What it is | Current status | What it proves |
|---|---|---|---|
| **Original bilingual corpus** | 150 generated claims, three broad categories, 2,251 files | Reproducible generated research asset; not in the current public runtime; not independently expert-approved | Data-generation and packaging infrastructure, plus why shortcut audits are essential |
| **Hardened defects vertical slice** | 48 generated journeys, 136 episodes, 1,148 attachments, longitudinal and negative cases | Stronger generated-reference benchmark held as a separate research release/archive, not the current default-branch runtime | That the task can be made nontrivial and that process-grounded adaptation can be evaluated under controlled synthetic conditions |
| **Deployed v20 flagship demonstration** | Two generated recurring-mould claims, nine source artifacts, deterministic typed reference pipeline, expert-review and reuse story | Live and browser-verified as a product demonstration | The complete product concept can be shown coherently from source claim to later-claim reuse |

The public deployment is a **research demonstration**, not an operational claim system. It uses generated claims and a deterministic reference pipeline. No real customer claim, legal decision, coverage decision, deadline calculation, or customer contact is authorized.

---

## Truth-status legend

Every substantive capability in this document is classified using one of the following labels.

| Label | Meaning |
|---|---|
| **Implemented and verified** | The capability exists in the current inspected code or deployment and has direct test, browser, API, or artifact evidence. |
| **Implemented but not fully verified** | Code exists, but the relevant behavior is not covered by an aligned current release gate, or the deployment differs from the source. |
| **Prototype / generated-reference only** | The behavior is demonstrated with generated inputs, static reference logic, simulated reviewers, hard-coded evaluation outputs, or archived research fixtures. It is not evidence of real-world validity. |
| **Planned** | The design or interface exists only in prompts, papers, archived branches, or backlog documents. |
| **Rejected / abandoned** | The approach was tried and found misleading, unsafe, weak, too complex, or inconsistent with the north star. It should not be revived without new evidence. |

Do not use “implemented” as a synonym for “validated.” Do not use “agentic” as a synonym for “model-driven.” Do not use “reviewed” when the reviewer was simulated. Do not use “realistic” when the only evidence is visual plausibility judged by the project author.

---

## Table of contents

1. [The mission](#1-the-mission)
2. [Why CasePath exists operationally](#2-why-casepath-exists-operationally)
3. [Current project truth](#3-current-project-truth)
4. [The data and benchmark landscape](#4-the-data-and-benchmark-landscape)
5. [Synthetic claim generation and artifact realism](#5-synthetic-claim-generation-and-artifact-realism)
6. [Current and historical agent architectures](#6-current-and-historical-agent-architectures)
7. [What must remain deterministic](#7-what-must-remain-deterministic)
8. [Process discovery](#8-process-discovery)
9. [Process-derived evidence and document requirements](#9-process-derived-evidence-and-document-requirements)
10. [Swiss-law grounding](#10-swiss-law-grounding)
11. [Historical claim retrieval](#11-historical-claim-retrieval)
12. [Expert feedback, reviewed memory, and shared learning](#12-expert-feedback-reviewed-memory-and-shared-learning)
13. [Evaluation and research findings](#13-evaluation-and-research-findings)
14. [Do not rediscover](#14-do-not-rediscover)
15. [UX journey and design history](#15-ux-journey-and-design-history)
16. [Deployment and release history](#16-deployment-and-release-history)
17. [Model and cost constraints](#17-model-and-cost-constraints)
18. [Repository map](#18-repository-map)
19. [Canonical contracts and compact examples](#19-canonical-contracts-and-compact-examples)
20. [Precise current-state table](#20-precise-current-state-table)
21. [Irreducible research questions](#21-irreducible-research-questions)
22. [Immediate next milestone](#22-immediate-next-milestone)
23. [First 60 minutes](#23-first-60-minutes)
24. [Glossary](#24-glossary)
25. [Operating rules for future collaborators](#25-operating-rules-for-future-collaborators)
26. [Appendix A: evidence and artifact registry](#appendix-a-evidence-and-artifact-registry)
27. [Appendix B: known defects and contradictions](#appendix-b-known-defects-and-contradictions)
28. [Appendix C: release and research evolution](#appendix-c-release-and-research-evolution)
29. [Appendix D: capability claim matrix](#appendix-d-capability-claim-matrix)
30. [Appendix E: adversarial handoff quality check](#appendix-e-adversarial-handoff-quality-check)

---

# 1. The mission

## 1.1 North star

CasePath is not primarily a classifier, a missing-document detector, a next-action predictor, or a polished claims dashboard.

Its north star is:

> **Given the customer’s first claim message and actual attachments, coordinated agents should infer the complete claim-handling process, derive the evidence and document requirements from that process and relevant Swiss law, retrieve useful historical experience, allow an expert to validate or correct the result, and turn validated cases into reusable organizational knowledge that improves future claims.**

The intended loop is:

```text
Claim intake
→ Understand message and attachments
→ Research Swiss tenant law
→ Construct a complete claim-specific process graph
→ Derive a process-grounded evidence and document model
→ Retrieve useful historical claims
→ Expert review
→ Approved case memory
→ Candidate reusable process knowledge
→ Regression testing and governance
→ Updated knowledge base
→ Future claim benefits
```

The central causal relationship is:

> **The process determines what must be established. Evidence and documents exist to establish those facts.**

This relationship must remain visible in:

- the problem formulation;
- canonical schemas;
- model and agent contracts;
- process graph;
- document checklist;
- expert-review interface;
- benchmark targets;
- evaluation;
- and product experience.

If process and checklist are predicted independently, CasePath has drifted from its defining idea.

## 1.2 Bounded operational purpose

The intended operational contribution is to prepare a claim for competent human handling. CasePath may:

- organize the original submission;
- expose supported, unknown, and conflicting facts;
- propose a claim-specific handling process;
- identify what evidence could resolve each decision;
- avoid asking again for evidence already present;
- surface relevant official sources and reviewed experience;
- record expert corrections;
- and propose governed updates to reusable knowledge.

It must not, without separate institutional and operational authorization:

- give legal advice;
- decide insurance coverage;
- calculate or guarantee legal deadlines;
- determine legal merits;
- automatically deny or accept a claim;
- contact a customer;
- autonomously escalate a case;
- or change shared organizational procedure from one unreviewed or one-off event.

## 1.3 What is scientifically interesting

The core scientific problem is not “can a model produce a plausible claim summary?” It is whether a system can recover and maintain a useful, inspectable coupling between:

```text
observable claim facts
→ operational decisions
→ process branches
→ evidence needs
→ expert corrections
→ reusable organizational rules
```

The project has explored at least three research formulations:

1. **Claim-readiness planning:** infer the process state, unresolved fact, evidence needed now, and next safe action.
2. **Claim-specific process and evidence reasoning:** infer the complete process graph and derive evidence from reached decisions.
3. **Fixed-workflow playbook induction from reviewed contrasts:** learn the non-default conditions inside an approved workflow while retaining deterministic execution and regression gates.

These formulations are related, but not interchangeable. The deployed v20 product currently emphasizes the second. Several paper artifacts emphasize the first or third. A new paper or experiment must explicitly select one research question instead of combining all three.

---

# 2. Why CasePath exists operationally

## 2.1 The real insurance problem

Experienced claim handlers carry a large amount of procedural knowledge in their heads. For an incoming tenant-law claim, they implicitly know:

- whether the message describes an actual dispute;
- whether the issue falls within the relevant legal and organizational scope;
- which questions must be answered before another question becomes meaningful;
- which facts are already supported;
- which facts are merely alleged;
- which documents are relevant to the reached branch;
- whether a document is sufficient, partial, conflicting, or irrelevant;
- which legal sources constrain the handling path;
- which previous claims are useful analogies;
- where uncertainty must remain open;
- and when a case is ready for specialist or expert action.

Conventional intake forms and static category checklists flatten that reasoning. They ask the same questions too early, request documents for inactive branches, omit evidence required by exceptions, and force experts to reconstruct the process repeatedly.

The operational unit is therefore not a category label. It is the **claim-specific path from incomplete submission to a safely actionable state**.

## 2.2 Tacit knowledge as a living playbook library

CasePath aims to convert repeated expert behavior into a living, expert-validated organizational playbook library.

A playbook should capture:

- the allowed process structure;
- decision questions;
- branch conditions;
- evidence goals;
- accepted evidence alternatives;
- legal or policy sources;
- ownership and handoff points;
- exceptions;
- effective dates;
- review history;
- and rollback information.

The library should not silently learn every observed action. Operational traces contain mistakes, local habits, convenience shortcuts, and context that may not generalize. Observed behavior is evidence for a candidate, not authority.

## 2.3 Practical value hypothesis

The practical hypotheses are:

- **Less repetitive reasoning:** experts do not rebuild the same procedural logic from scratch.
- **More consistent handling:** similar claims expose similar decisions and evidence rationale.
- **Faster onboarding:** new handlers can inspect the process and supporting sources.
- **Fewer unnecessary requests:** evidence is requested only for reached decisions and only if absent or insufficient.
- **Better first-request completeness:** related needs can be compiled from the active process rather than discovered through repeated follow-up.
- **Reusable precedent:** reviewed cases become inspectable organizational memory.
- **Transparency:** every important conclusion can point to source evidence, process logic, and authority.
- **Continual improvement:** repeated compatible corrections may become tested, approved playbook changes.

These are still hypotheses for real operations. Generated simulations and deterministic demos do not establish actual workload reduction, customer-friction reduction, legal validity, or transfer to production claims.

---

# 3. Current project truth

## 3.1 Authoritative current product

The currently deployed product is CasePath v20 at:

- Frontend: <https://casepath-swiss-claim-lab.onrender.com/>
- API: <https://casepath-agentic-api.onrender.com/>
- Canonical browser evidence: <https://casepath-guided-canonical-qa.onrender.com/>

The product code baseline is:

```text
Repository: KumarNavish/KumarNavish.github.io
Product commit: a867bb506d8e3f790806fc21f2a24a011c1cd0bc
Frontend release marker: 20.0.0
API pipeline release: 15.0.0
```

The repository is a broader personal-site repository, not a dedicated CasePath repository. The root README describes a portfolio system and is not a reliable CasePath entry point. CasePath lives mainly under:

```text
casepath/
casepath-api/
casepath-qa/
```

## 3.2 Deployment SHA reality

The production components are not all on one SHA.

| Component | Live SHA | Status | Interpretation |
|---|---:|---|---|
| Frontend | `a867bb506d8e3f790806fc21f2a24a011c1cd0bc` | Live | Current v20 focused product |
| API | `550c42175c2dfa432dd32eb4c5f82361ce1c2f25` | Live | Earlier code SHA, but API code did not change during the v20-only frontend pass |
| Canonical QA | `7be18c72f353366930cd5dcace637884e06e63a7` | Live | QA-only patch commit; not current product master |

This is not necessarily a functional mismatch, but it is a release-governance mismatch. The stale `casepath/release.json` says frontend and API must report the same release before acceptance; that contract is not currently satisfied.

## 3.3 What the deployed product actually demonstrates

### Implemented and verified

The v20 browser gate verified an uninterrupted journey that:

1. opens an intentional claim shell;
2. displays one generated customer message and six inspectable source attachments;
3. renders a six-page PDF and a source photograph;
4. starts analysis through one action;
5. shows source-level backend events;
6. shows one current specialist while the source claim remains visible;
7. makes an 11-stage process graph the dominant artifact;
8. attaches evidence status to process decisions;
9. shows three reviewed-reference precedents at the relevant decision;
10. allows one consequential expert correction beside the graph;
11. shows reviewed memory, expert correction, and shared playbook change;
12. opens a second generated claim;
13. shows a before/after effect from the reviewed memory and v4 playbook;
14. produces two separate backend runs;
15. works without page-level overflow at 390 px and 320 px;
16. reports no browser console, page, or public request failures;
17. resets the demo to playbook v3 after the run.

The focused gate reported 57 passing checks and zero failures.

### Prototype / generated-reference only

The following are demonstrated, but not validated as real intelligence or real organizational learning:

- claim understanding;
- legal question formulation;
- legal source selection;
- process graph generation;
- evidence model generation;
- historical retrieval;
- verification;
- expert-reviewed memory;
- playbook promotion;
- protected regression;
- and later-claim benefit.

In the public runtime, these are produced by a deterministic typed reference pipeline for two generated cases. Several evaluation values are hard-coded reference outputs.

## 3.4 Current public data boundary

The public runtime contains exactly two claims:

- `DEF-027-E0-DEMO`: flagship recurring-mould claim.
- `DEMO-MOULD-002`: later recurring-condensation claim.

It exposes nine artifacts:

- six for the flagship claim;
- three for the later claim.

The public runtime is not a browser over the 150-claim corpus or the 48-journey benchmark.

## 3.5 Current API profile

The deployed API identifies itself as:

```text
profile: full-process-reference-agents
orchestrator: casepath-reference-orchestrator/15.0
implementation: typed_reference_agent
generated_data_only: true
real_claims_approved: false
```

The implementation is a deterministic Python pipeline with typed event records. It uses a background thread and deliberate pacing to create an observable product narrative. It does not currently invoke a language model.

## 3.6 Status of major architectural claims

| Claim | Truth status | Evidence |
|---|---|---|
| The public product uses real backend run events | **Implemented and verified** | Browser gate observes two API-created runs and source-level events |
| The public product runs multiple model-driven specialist agents | **Prototype / generated-reference only** | Specialist stages are deterministic functions labeled `typed_reference_agent` |
| The public product uses LangChain/LangGraph | **Rejected as a statement of current deployment** | No LangChain dependency in current `requirements.txt`; no LangChain source in current master |
| The public product uses Nemotron through OpenRouter | **Rejected as a statement of current deployment** | No model call path in current deployed API; historical implementation only |
| The process graph is claim-specific | **Implemented and verified for two handcrafted reference claims** | Flagship and later graph differ; not a general inference result |
| The evidence checklist is derived from process nodes and facts | **Implemented and verified** | Each current evidence item links to `node_id`, `fact_id`, and `why`; validator and browser checks |
| Swiss law shapes the process | **Prototype / generated-reference only** | Static official-source registry and handcrafted operational mapping; no qualified expert approval |
| Historical cases are retrieved by useful process dimensions | **Prototype / generated-reference only** | Deterministic ranking and three static references; reviewed memory is prioritized after review |
| One expert-reviewed claim changes shared knowledge | **Not the intended rule; public demo simulates a promoted v4 candidate** | Public candidate uses generated support and hard-coded evaluation; not an actual one-case production promotion |
| Knowledge is durable | **Not implemented for production** | SQLite defaults to `/tmp`, which is ephemeral on Render |
| The public runtime processes 150 claims | **False** | Two claims in `data.py` and build smoke |
| The original 150-claim corpus is an approved benchmark | **False** | Generated candidate; distribution and publication flags false |
| The hardened vertical slice is operationally approved | **False** | Manifest explicitly says not approved for operational use |

---

# 4. The data and benchmark landscape

## 4.1 Do not collapse the three datasets

### A. Original bilingual corpus

**State:** Prototype / generated-reference only.

The original corpus contains:

| Property | Value |
|---|---:|
| Claims | 150 |
| Languages | 75 German (`de-CH`), 75 English |
| Categories | 3 |
| Claims per category | 50 |
| Receipt-bound files | 2,251 |
| Scenario or near-duplicate groups | 28 |
| Independent expert review | Not performed |
| Distribution allowed | No |
| Publication eligible | No |

Categories:

- `defect_mold_heating`
- `lease_termination_dispute`
- `rent_increase_dispute`

Artifact families include:

- customer messages;
- attachments;
- bundled PDFs;
- canonical JSON;
- process graphs;
- checklists;
- reference answers;
- provenance records.

Reported reproducibility for the original package:

```text
2,633 passed
22 skipped
0 failed
byte-identical deterministic rebuild
```

The reported source commit was `7bebdf3f9fc35641ee91262f61180b27362e99cc`, but that SHA is not present in the current inspected GitHub repository. Treat it as external release provenance until the corresponding repository or archive is recovered and independently matched.

#### Original corpus defects

The integrity audit found no missing receipt-bound file, but task validity was weak:

- subject-only category accuracy was 95.3%;
- each category reused one graph skeleton;
- all 150 claims were in `submitted` state;
- all current nodes were category intake nodes;
- no negative or out-of-scope disputes existed;
- 105 claims had no attachment, 33 had one, and 12 had two;
- ground truth was generated and not independently expert-approved.

A high integrity score therefore did not imply a scientifically strong benchmark.

### B. Hardened defects vertical slice

**State:** Prototype / generated-reference only; stronger research benchmark.

Contract:

```text
casepath.defects-vertical-slice-benchmark/1.0.0
```

Core counts:

| Property | Value |
|---|---:|
| Journeys | 48 |
| Longitudinal episodes | 136 |
| Languages | 68 English, 68 German |
| Attachments | 1,148 |
| Attachment-decisive episodes | 97 |
| Hard-negative episodes | 16 |
| New-pattern episodes | 48 |
| Expert-review items | 30 |
| Challenge cases in expert-ready extension | 24 |

Scenario families:

- 8 ordinary recurring-mould cases;
- 6 moisture-ingress cases;
- 4 water-leak cases;
- 6 heating-failure cases;
- 16 withheld ventilation-pattern cases, deliberately retaining the broad `mould_recurrence` subtype;
- 8 negative or boundary cases:
  - no current dispute;
  - advisory only;
  - hotel guest;
  - owner-occupied property;
  - wrong jurisdiction;
  - duplicate claim;
  - insufficient tenancy/dispute evidence;
  - adjacent rent issue after a resolved defect.

The vertical slice contains:

- 28 distinct process paths;
- 12 distinct current process nodes;
- staged evidence episodes;
- conflicting evidence;
- source-group identifiers;
- language and surface-family variation;
- attachment-decisive cases;
- hidden generation provenance;
- observable packages;
- bundled PDFs;
- reference plans;
- and ground-truth objects.

It is not currently committed under the public product’s default branch. Locate it through the archived `CasePath_Defects_Expert_Ready_Agent` release or reconstruct it from its release manifest and checksums before treating it as locally available.

### C. Deployed flagship demonstration

**State:** Implemented and verified as a product demo; generated-reference only as research evidence.

| Property | Value |
|---|---:|
| Claims | 2 |
| Flagship source artifacts | 6 |
| Later-claim source artifacts | 3 |
| Process main-spine nodes | 11 |
| Flagship evidence items | 20 |
| Static historical references | 3 |
| Browser acceptance checks | 57 |
| Model calls | 0 |

The deployed demo is intentionally narrow. It should not be reported as benchmark coverage.

## 4.2 Observable versus hidden information

### Observable Claim Package

A downstream model or agent may see only information available at intake:

- the first customer message;
- submitted PDFs, images, emails, forms, and other files;
- filenames and media types if genuinely present in intake;
- received timestamps and allowed metadata;
- extracted text or visual descriptions derived from those files;
- source spans and artifact identifiers;
- approved public context that is explicitly supplied.

The canonical state must be derived from this observable package.

### Hidden reference information

Generation and evaluation may retain:

- category and subcategory labels;
- process graph;
- branch conditions;
- current process state;
- expected facts;
- evidence applicability;
- reference document requirements;
- reference next action;
- final outcome;
- generation prompt;
- template ID;
- source group;
- renderer family;
- provenance;
- hidden response schedule;
- and benchmark split metadata.

### Why leakage is forbidden

If hidden labels, generator names, scenario templates, or expected actions enter model-visible fields, the benchmark stops measuring claim understanding. The system can recover the answer from construction artifacts rather than from the customer submission.

Leakage checks must cover:

- filenames;
- PDF metadata;
- visible headers and footers;
- embedded “generated,” “synthetic,” “sample,” or scenario labels;
- schema field ordering;
- prompt-template phrases;
- author or producer metadata;
- duplicate textual fragments;
- source-group overlap;
- and URLs or internal IDs that encode the target.

The current public artifact generator visibly marks PDFs as generated fictional documents. That is acceptable for a disclosed demo, but it means those same files are not suitable as leakage-clean benchmark inputs without rerendering.

## 4.3 Benchmark object structure

A vertical-slice manifest record points to:

```text
benchmark/packages/<claim>/<episode>.json          observable package
benchmark/bundles/<claim>/<episode>.pdf            bundled observable artifact
benchmark/ground_truth/<claim>/<episode>.json       hidden reference state
benchmark/reference_plans/<claim>/<episode>.json    hidden reference process and evidence plan
```

A journey groups multiple chronological episodes. Each episode may add, satisfy, contradict, or supersede evidence from earlier episodes. The evaluation must enforce prefix-only information: no future artifact may influence an earlier prediction.

## 4.4 Quality and reproducibility status

### Original corpus

- Byte-identical rebuild reported.
- 2,633 passed tests reported.
- Internal integrity checks passed.
- No independent expert approval.
- Distribution and publication disabled.
- Task validity failed important shortcut tests.

### Hardened vertical slice

- 714 automated tests reported in the expert-ready extension.
- 47 strict JSON schemas.
- 136 packages, plans, and ground-truth objects validated.
- 48 journeys.
- 30 disagreement-aware targets.
- 24 challenge cases.
- 15 browser checks.
- No qualified domain-review evidence.
- Some report snapshots disagree slightly on exact split-level metrics; preserve report version and do not silently reconcile.

### Deployed v20 demonstration

- 57 focused production checks passed.
- Two real API runs created through the UI.
- No browser console, page, or request failures in the retained gate.
- The current default-branch QA script contains stale assumptions and should not be assumed to reproduce that pass without repair.
- API unit tests target a legacy pipeline module rather than `pipeline_v15.py`.

---

# 5. Synthetic claim generation and artifact realism

## 5.1 Why generated claims are necessary

Real insurance claims contain personal, confidential, legally sensitive, and operationally restricted data. Initial research therefore uses generated claim packages and public legal sources.

Generated data permits:

- complete hidden process and evidence labels;
- counterfactual variations;
- staged longitudinal episodes;
- source-group isolation;
- deliberate contradictions;
- rare negative cases;
- controlled evidence arrival;
- exact provenance;
- and public reproducibility.

Generated data is a means to build and falsify the research method. It is not evidence that the method transfers to real claims.

## 5.2 Generation architecture

The hardened research release uses a prompt- and schema-driven generator with deterministic post-processing. The intended pipeline is:

```text
scenario specification
→ claim-message prompt
→ attachment-content prompts
→ model- or template-generated semantic content
→ deterministic normalization
→ schema validation
→ process/reference-plan generation
→ document rendering
→ PDF/image/email packaging
→ cross-document consistency checks
→ leakage and shortcut checks
→ manifest and provenance freeze
```

The exact released generator is not available in the current default branch. The archived `benchmark.py`, manifests, schemas, renderers, and release tools are therefore part of the benchmark handoff, not the public v20 product tree.

## 5.3 Current public artifact generator

The deployed demo’s `casepath-api/generate_artifacts.py`:

- deterministically creates a six-page lease;
- creates a two-page chronology;
- creates a delivery-receipt PDF;
- writes notification and management-response email files;
- creates later-claim correspondence;
- initially generates procedural images;
- and is followed by `replace_photographic_evidence.py`, which substitutes checksum-verified licensed photographs.

The Render build verifies:

- required files exist;
- Wikimedia attribution exists;
- expected photo hashes match;
- artifact metadata matches file bytes;
- the primary claim has six artifacts;
- the runtime has exactly two claims.

## 5.4 Major lesson: visible inputs must resemble operations

A benchmark-visible package must not contain generation artifacts. In particular, the evaluated model should not see:

- “synthetic”;
- “generated”;
- “sample”;
- “fictional”;
- benchmark category names;
- answer-bearing scenario IDs;
- renderer labels;
- or hidden generation metadata.

The current demo lease and related PDFs include visible “Generated fictional document – CasePath demo” footers and generated-author metadata. This is an honest public-demo disclosure, but it violates the stricter benchmark realism standard.

## 5.5 Current realism weakness

**State:** Prototype / generated-reference only.

The flagship package is more operationally inspectable than earlier “safe preview” panels, but it is not yet strong enough for a blind realism claim.

Current weaknesses include:

- machine-perfect typesetting;
- explicit generated-document footers;
- unusually complete lease language tailored to the benchmark;
- overly clean correspondence;
- limited scan noise and administrative clutter;
- no independent realism rating;
- no realistic logos, signatures, redactions, stamps, or inconsistent formatting where appropriate;
- a small set of photographs selected or generated for demonstration rather than sourced from an operational distribution;
- and only two public claim packages.

## 5.6 Desired artifact quality bar

### Multi-page leases

- complete and internally consistent;
- realistic clauses and page density;
- plausible formatting and signature pages;
- no answer-bearing benchmark language;
- appropriate metadata scrubbed;
- OCR and visual layout both usable;
- page-level source references stable.

### Landlord letters and notices

- realistic letterhead and dates;
- imperfect but plausible phrasing;
- proper sender and recipient context;
- attachments and references consistent across files;
- no hidden branch label in filenames.

### Invoices and inspection reports

- line items, identifiers, dates, author, limitations, and measurement context;
- realistic uncertainty;
- conclusions not stronger than the observations;
- process implications kept separate from report content.

### Email chains

- headers, threading, quotations, and timestamp consistency;
- occasional irrelevant text and forwarding artifacts;
- deduplication and source selection tested.

### Photographs

- high resolution;
- plausible phone-camera perspective and lighting;
- no procedural drawing or stylized placeholder;
- visually relevant but not magically diagnostic;
- location and date consistency;
- sufficient ambiguity to require technical interpretation.

### Cross-document consistency

- names, addresses, dates, rooms, reported events, and attachment references agree unless contradiction is deliberately part of the case;
- deliberate conflicts are registered in hidden provenance and detectable from observable files;
- no impossible sequence of events;
- no future evidence in earlier episodes.

---

# 6. Current and historical agent architectures

## 6.1 Current deployed architecture

**State:** Implemented and verified as deterministic reference orchestration.

The current public API uses:

```text
ClaimPipeline
→ one run-scoped shared context
→ ordered typed specialist stages
→ deterministic validators
→ review pause
→ memory and candidate storage
```

The orchestrator is:

```text
casepath-reference-orchestrator/15.0
```

The profile is:

```text
full-process-reference-agents
```

Each emitted event records:

- stage;
- agent;
- status;
- implementation;
- model identifier;
- orchestrator identifier;
- shared-context identifier;
- validator version;
- prompt version;
- and stage-specific payload.

The event record is valuable even though the current “agents” are deterministic functions. It establishes a replaceable event and artifact contract.

## 6.2 Specialist stages in the deployed reference

### 1. Attachment Parsing Agent

| Field | Current contract |
|---|---|
| Purpose | Inventory and parse the customer message and source artifacts |
| Input | Observable claim package and artifact registry |
| Output | `parsed_submission` / source package |
| Shared context | Run-scoped artifact list |
| Tools | Local file access, PDF page metadata, email text, predefined extraction |
| Model dependency | None in current deployment |
| Validation | Artifact IDs, media types, pages, extraction availability |
| Downstream consumer | Claim Understanding Agent |
| Swap interface | Produce the same source-linked parsed-submission contract |

### 2. Claim Understanding Agent

| Field | Current contract |
|---|---|
| Purpose | Separate supported facts, allegations, conflicts, and unknowns |
| Input | Parsed submission |
| Output | `canonical_claim_state` with source-linked facts |
| Shared context | Accepted source package plus fact registry |
| Tools | Deterministic fact constructor in current deployment |
| Model dependency | None in current deployment |
| Validation | Fact IDs, states, confidence, source refs, allowed fact registry |
| Downstream consumer | Legal research, process discovery, evidence |
| Swap interface | Any model may replace it if it emits the same canonical state and provenance |

### 3. Legal-query formulation

The current public pipeline does not expose a separate model-driven query agent. Legal questions are created in the research stage from the accepted claim state.

| Field | Current contract |
|---|---|
| Purpose | Formulate claim-specific legal and handling questions |
| Input | Canonical claim state |
| Output | Question list |
| Model dependency | None |
| Validation | Question IDs and source-to-node mapping |
| Downstream consumer | Swiss-law research |
| Swap interface | Return typed questions without legal conclusions beyond evidence |

### 4. Legal Research Agent

| Field | Current contract |
|---|---|
| Purpose | Select official sources and convert them into handling implications |
| Input | Claim state and legal questions |
| Output | `legal_context` |
| Shared context | Facts plus static law registry |
| Tools | Static in-memory registry search |
| Model dependency | None |
| Validation | Official-source IDs, URLs, node links, explicit review status |
| Downstream consumer | Process Discovery and inspector UI |
| Swap interface | Produce source, passage/summary, interpretation, and process implication separately |

### 5. Process Discovery Agent

| Field | Current contract |
|---|---|
| Purpose | Produce the complete handling graph and current-claim overlay |
| Input | Claim state and legal context |
| Output | `process_graph` |
| Shared context | Facts, legal sources, versioned playbook |
| Tools | Deterministic graph constructors for flagship and later variants |
| Model dependency | None |
| Validation | Node uniqueness, edge validity, current node, blocked states, branch integrity |
| Downstream consumer | Evidence model, review UI, verification |
| Swap interface | Emit the canonical graph; do not change frontend or checklist contracts |

### 6. Document Requirements Agent

| Field | Current contract |
|---|---|
| Purpose | Attach evidence requirements to process decisions |
| Input | Process graph, claim state, source inventory |
| Output | `evidence_model` / checklist |
| Shared context | Node and fact registries |
| Tools | Deterministic item constructors |
| Model dependency | None |
| Validation | Every item links to existing node and fact; no repeat request; status and alternatives valid |
| Downstream consumer | Decision inspector, derived document view, verification |
| Swap interface | Preserve `node_id`, `fact_id`, `why`, alternatives, status, and source refs |

### 7. Historical Claims Agent

| Field | Current contract |
|---|---|
| Purpose | Retrieve up to three useful prior cases at the unresolved decision |
| Input | Current claim, process state, evidence gap, reviewed memory |
| Output | `precedents` |
| Shared context | Current node and stored memories |
| Tools | Deterministic score and static historical registry |
| Model dependency | None |
| Validation | Current claim excluded; reviewed memory prioritized; three distinct cases |
| Downstream consumer | Decision inspector and later-claim reasoning |
| Swap interface | Return typed relevance dimensions and reviewed status, not only similarity score |

### 8. Verification Agent

| Field | Current contract |
|---|---|
| Purpose | Reject unsupported relationships and verify the playbook before review |
| Input | Claim state, law, graph, checklist, precedents |
| Output | `verification_report` |
| Tools | Deterministic validators |
| Model dependency | None |
| Validation | Observable grounding, graph integrity, law links, evidence links, no self-retrieval |
| Downstream consumer | Expert review |
| Swap interface | Keep accepted and rejected proposals explicit |

### 9. Expert Feedback Agent

| Field | Current contract |
|---|---|
| Purpose | Record one consequential expert evidence-order decision |
| Input | Generated playbook and selected review choice |
| Output | Reviewed graph/checklist, typed review record |
| Model dependency | None |
| Validation | Allowed choice, recomputed downstream artifacts |
| Downstream consumer | Memory and knowledge consolidation |
| Swap interface | Typed operations against canonical artifacts rather than unstructured notes |

### 10. Knowledge Consolidation Agent

| Field | Current contract |
|---|---|
| Purpose | Save reviewed case memory and create a candidate reusable playbook change |
| Input | Reviewed run and correction |
| Output | Memory, candidate patch, v4 reference result |
| Model dependency | None |
| Validation | Support, target tests, protected tests, version and rollback fields |
| Downstream consumer | Later claim |
| Swap interface | Separate immediate memory from shared-rule proposal |

## 6.3 Historical LangChain/Nemotron implementation

**State:** Implemented in an archived or external prototype, not in current master or deployment.

Archived source evidence includes a `LangChainAgentSuite` using:

- `langchain.agents.create_agent`;
- `ToolStrategy`;
- `ChatOpenAI`;
- a `SharedRunContext`;
- structured Pydantic outputs;
- OpenRouter;
- NVIDIA-only provider routing;
- provider fallback disabled;
- zero automatic retries;
- and a shared model across specialist agents.

One historical model identifier is:

```text
nvidia/nemotron-3-ultra-550b-a55b:free
```

Earlier v3 release artifacts specify:

```text
nvidia/nemotron-3-super-120b-a12b:free
```

The two model IDs represent configuration drift across project generations. The current public runtime uses neither.

The historical architecture included eight explicit model-driven agents:

1. attachment parsing;
2. claim interpretation;
3. legal query formulation;
4. legal research;
5. process graph proposal;
6. checklist proposal;
7. historical precedent proposal;
8. knowledge consolidation proposal.

The architectural principle remains sound:

> **Specialist agents may change. Canonical data contracts, validators, audit records, and human-control boundaries should not.**

Before reintroducing this path:

- recover the exact source into the current repository;
- choose one model identifier;
- pin dependencies;
- make the provider optional;
- add cached fixtures;
- run deterministic tests first;
- run one authorized model-call smoke;
- compare output against the reference contract;
- and never claim that a live model is deployed until the public run record proves it.

## 6.4 Model/provider abstraction status

| Capability | State |
|---|---|
| Abstract replaceable-agent design | **Implemented in historical prototype and planned for current architecture** |
| Current public provider selection | **Not applicable; no model call** |
| OpenRouter integration | **Historical implementation only** |
| Nemotron live call | **Not verified** |
| Current canonical model interface in master | **Missing** |
| Deterministic fallback | **Current public runtime is itself deterministic** |
| Call cache | **Historical design; not current v15** |

## 6.5 Orchestrator replacement principle

A replacement orchestrator may change:

- scheduling;
- which agent runs in parallel;
- prompting;
- retries;
- model provider;
- or tool implementation.

It must not silently change:

- observable-input boundary;
- canonical state schema;
- source-reference requirements;
- process graph contract;
- evidence-item contract;
- review operation contract;
- release gates;
- versioning;
- or audit semantics.

---

# 7. What must remain deterministic

“Fully agentic” does not mean giving models control over every layer.

## 7.1 Deterministic responsibilities

Deterministic infrastructure must own:

- schema validation;
- allowed enum values;
- artifact identity and hashes;
- source provenance;
- observable-versus-hidden separation;
- fact-state vocabulary;
- graph integrity;
- dangling-node and dangling-edge checks;
- evidence-to-node linkage;
- evidence-to-fact linkage;
- prevention of repeat requests;
- evidence-state transitions;
- versioning;
- effective dates;
- permissions;
- model-call quotas;
- release and promotion gates;
- protected regression replay;
- audit logging;
- rollback;
- and final human authorization.

## 7.2 Agent responsibilities

Agents may propose:

- document parses;
- fact values and confidence;
- legal questions;
- retrieved sources;
- operational interpretations;
- process nodes and branches;
- evidence alternatives;
- precedent ranking;
- candidate knowledge patterns;
- and explanations.

An agent proposal is not accepted merely because it is fluent or internally consistent.

## 7.3 Human responsibilities

Qualified humans must control:

- legal and operational validity;
- allowed scope;
- disputed alternatives;
- expert-review approval;
- candidate knowledge promotion;
- exceptions to ordinary regression thresholds;
- and authorization for real-data or customer-facing use.

## 7.4 Three-valued logic

Process conditions should distinguish:

```text
true
false
unknown
```

A known false literal should make a conjunction false even if another literal is unknown. An unknown higher-priority condition should block a lower-priority branch only when no known literal disproves it. Optional positive-trigger branches should remain inactive until every required positive trigger is established.

This lesson came from a prior safety-critical defect: an irrelevant optional branch could block an ordinary claim because one fact was unknown even though another known fact made the branch impossible.

## 7.5 Fail-closed execution

When a controlling fact is unknown or conflicting:

- do not activate a consequential branch;
- do not treat the process as complete;
- do not remove evidence requirements that could resolve the uncertainty;
- and do not infer a legal conclusion from absence of evidence.

Abstention is an operational result, not a system failure.

---

# 8. Process discovery

## 8.1 Category template versus claim-specific process

A **category template** says:

```text
this is a mould claim
→ use the mould graph
```

A **claim-specific process instance** says:

```text
this is an in-scope tenant dispute
→ no urgent health risk is currently supported
→ notification exists
→ recurrence is supported
→ causation is disputed
→ responsibility and remedy must remain blocked
→ technical evidence is the active loop
```

The first can be produced from a subject line. The second requires evidence, uncertainty, law, and branch conditions.

## 8.2 Desired process representation

The complete graph should represent:

- intake;
- legal and organizational scope;
- whether a dispute exists;
- urgency and safety;
- prerequisite facts;
- notification;
- defect or issue establishment;
- causation;
- responsibility;
- remedy;
- conditional evidence loops;
- escalation;
- resolution;
- terminal and out-of-scope states;
- and allowed alternative paths.

The output is the **complete handling graph**. The current claim’s position is an overlay:

- completed;
- current;
- blocked;
- available;
- conditional;
- inactive;
- not applicable.

Do not reduce process discovery to “what is the next blocker?” The next blocker is one view of the full graph.

## 8.3 Current public process graph

**State:** Implemented and verified for two reference variants.

The flagship main spine contains 11 nodes:

```text
Claim intake
→ Tenant-law scope
→ Existence of a dispute
→ Urgency and safety
→ Landlord notification
→ Defect and recurrence
→ Causation assessment
→ Responsibility
→ Remedy selection
→ Escalation
→ Resolution and closure
```

The flagship overlay places the claim at causation. Responsibility and remedy are blocked. Causation exposes four outcomes:

- building defect;
- use-related cause;
- mixed contribution;
- insufficient evidence.

The later v4 graph adds:

```text
Test the ventilation allegation
```

This makes an earlier implicit allegation an explicit decision and changes evidence ownership.

The graph is not inferred by a general model. It is deterministically constructed from two predefined case variants.

## 8.4 Benchmark lesson: category templates were artificially easy

The original 150-claim corpus used one graph skeleton per category. Process-node scores were therefore largely a category-recognition score.

The hardened vertical slice introduced:

- 28 distinct process paths;
- 12 current nodes;
- urgency variation;
- scope variation;
- dispute variation;
- notification and response variation;
- disputed causation;
- technical-assessment state;
- access state;
- evidence sufficiency;
- remedy state;
- repair monitoring;
- conciliation readiness;
- and negative/out-of-scope cases.

Reported generated-reference branch accuracy:

| Method | Branch accuracy |
|---|---:|
| Category-template baseline | 0.068 |
| Static process library | 0.705 |
| Generated reference contract | 1.000 |

The generated reference is an oracle contract, not a learned-method result.

## 8.5 Multiple valid graphs

Claims may admit more than one operationally valid path because:

- organizations sequence work differently;
- legal uncertainty supports alternatives;
- evidence types are substitutable;
- urgency can justify parallel actions;
- and experts can disagree on process preference without disagreeing on facts.

Evaluation should therefore support:

- accepted alternative graphs;
- set-valued targets;
- constraint validity;
- disagreement types;
- and expert adjudication.

Exact graph match is useful as a strict diagnostic but should not be the sole validity criterion.

## 8.6 Research boundary

The current public demo proves that a complete graph can be represented and used as the product’s organizing artifact. It does not prove that a model can infer such a graph from real claims or sparse operational traces.

The next process-discovery experiment must compare at least:

- category-template graph;
- supplied-library deterministic instantiation;
- equally informed direct graph predictor;
- process-aware model;
- and an oracle or adjudicated-state upper bound.



# 9. Process-derived evidence and document requirements

## 9.1 Canonical dependency chain

CasePath’s document logic must follow:

```text
Legal or operational requirement
→ Process question
→ Fact that must be established
→ Evidence capable of establishing the fact
→ Document or source type
→ Current evidence state
```

A checklist item without this chain is not a CasePath item. It is a category heuristic.

## 9.2 Evidence requirement versus document name

An evidence requirement is a factual goal, not a file label.

Example:

```text
Decision:
What caused the recurring mould?

Fact required:
Likely technical cause.

Evidence alternatives:
- independent technical assessment;
- moisture and temperature measurements;
- a sufficiently detailed specialist report;
- building-envelope assessment if the first assessment cannot distinguish the cause.

Current state:
Photos establish visible mould, but not causation.
```

Several artifacts may satisfy one evidence goal. One artifact may support several facts. A missing filename does not necessarily imply a missing fact.

## 9.3 Evidence states

The canonical state vocabulary should include:

| State | Meaning |
|---|---|
| `provided_sufficient` / sufficient | Present and adequate for the specific fact and decision |
| `provided_insufficient` / insufficient | Present but incomplete, unreliable, unreadable, or unable to establish the required fact |
| `missing` | Applicable and not present |
| `conditional` | Becomes applicable only if a registered branch condition is reached |
| `not_applicable` | Not required on the current path |
| `present_unreviewed` | Present but not yet assessed by the responsible human or validator |
| `conflicting` | Relevant sources disagree or support incompatible values |
| `unknown` | Applicability or sufficiency cannot yet be established |

The public v15 runtime directly uses five states:

```text
provided_sufficient
provided_insufficient
missing
conditional
not_applicable
```

`present_unreviewed` and a first-class checklist-level `conflicting` state are desirable schema extensions, but are not currently implemented in the deployed public checklist.

## 9.4 Current public evidence model

**State:** Implemented and verified for the flagship reference claim.

The flagship produces 20 process-grounded evidence items. Each item includes, where relevant:

- `item_id`;
- `title`;
- `node_id`;
- `fact_id`;
- `fact_label`;
- `why`;
- `status`;
- linked artifact IDs;
- legal source IDs;
- accepted alternatives;
- activation condition;
- required level;
- current-path flag.

The deployed validator checks:

- node exists;
- fact exists;
- reason exists;
- a provided artifact is not requested again;
- conditional items remain conditional;
- inactive-branch items are not requested;
- evidence alternatives are represented;
- and the graph contains the evidence-owning decision.

## 9.5 The no-repeat invariant

If a relevant artifact is already present, the system must not ask the customer to submit the same artifact again.

A present but insufficient artifact should be represented as:

```text
present
+ insufficient for the required fact
+ reason for insufficiency
+ possible way to strengthen or replace it
```

It should not be silently converted to `missing`.

## 9.6 Static category checklists are insufficient

The operational simulation on the hardened generated benchmark reported:

| Method | Unnecessary requests per journey |
|---|---:|
| Verified process-grounded patch | 0.000 |
| Static category checklist | 9.938 |

This is a controlled generated simulation, not a customer study. Its value is conceptual: static lists ask for items unrelated to the reached path, whereas process-grounded requirements can stop when a fact is already established or a branch is inactive.

## 9.7 Current product presentation

The v20 interface makes evidence secondary to the process:

- evidence state markers appear on process nodes;
- the selected decision inspector shows “What we know” and “Evidence that could resolve this”;
- the old standalone evidence-chain explanation is hidden from the primary view;
- a complete document list is available only through “View document needs”;
- and each derived document item links back to its process decision.

This is the correct product hierarchy.

## 9.8 What still needs work

- The public evidence model is handcrafted for two claims.
- Evidence equivalence is not learned.
- Sufficiency thresholds are not expert-approved.
- No real document-quality evaluation exists.
- Current reference artifacts often state exactly what the benchmark expects.
- Conflicting evidence is represented in facts but not fully propagated through a general evidence-state engine.
- No evaluation compares process-grounded checklist generation against an equally informed strong direct predictor on expert targets.

---

# 10. Swiss-law grounding

## 10.1 Intended pipeline

The legal grounding pipeline should be:

```text
Claim understanding
→ Claim-specific legal questions
→ Retrieval
→ Official sources and passages
→ Operational interpretation
→ Process implications
→ Evidence implications
```

The legal component is useful only when it changes or justifies a decision in the handling process.

## 10.2 Four distinct objects

Never collapse these objects:

1. **Official legal source**
   A statute, regulation, official guidance page, authority document, or approved internal source.

2. **Retrieved passage**
   The exact relevant provision or passage, with version, page or section, URL, and retrieval metadata.

3. **Operational interpretation**
   A plain-language statement of what the source may imply for handling the bounded claim.

4. **Expert-approved handling rule**
   A versioned organizational rule approved for use in a defined scope.

A model-generated operational interpretation is not an official source. An official source does not automatically determine an organizational process. A retrieved passage does not become a shared playbook rule without review.

## 10.3 Current public legal implementation

**State:** Prototype / generated-reference only.

The public v15 pipeline creates five legal questions and selects from a static registry. Current sources include references to:

- Swiss Code of Obligations Article 256;
- Article 257g;
- Articles 259a and following;
- official information concerning conciliation authorities;
- and generated operational principles about disputed causation and least-burdensome competent evidence.

The mapping attaches sources to process nodes. The UI shows small law markers and can explain why a decision exists.

This is not a live vector database, web retrieval, or agentic legal RAG system. It is a static question-led source registry plus handcrafted operational translation.

## 10.4 Review status

The current pipeline explicitly records that its operational translation has not been approved by a qualified Swiss tenant-law reviewer.

This status must remain visible in technical detail and in any research claim. Do not describe the graph as legally correct.

## 10.5 Desired legal-RAG contract

A replacement legal agent should output:

```json
{
  "question_id": "q_causation",
  "question": "What must be established before responsibility for recurring mould is assigned?",
  "sources": [
    {
      "source_id": "fedlex_or_256",
      "source_type": "official_statute",
      "jurisdiction": "CH",
      "version_date": "YYYY-MM-DD",
      "url": "...",
      "passage": "...",
      "location": "Article 256"
    }
  ],
  "operational_interpretation": {
    "text": "Keep causation unresolved until competent evidence supports a branch.",
    "status": "model_proposed_not_expert_approved"
  },
  "process_implications": [
    {
      "node_id": "causation",
      "effect": "required_before_responsibility"
    }
  ]
}
```

## 10.6 Retrieval quality requirements

Evaluation should measure:

- official-source precision;
- passage relevance;
- jurisdiction and effective-date correctness;
- unsupported interpretation rate;
- process-node linkage accuracy;
- and expert agreement with the operational implication.

A legal RAG system that retrieves correct text but links it to the wrong process question has failed.

---

# 11. Historical claim retrieval

## 11.1 Purpose

Retrieving three prior claims is intended to provide organizational memory at the decision where it matters.

The target is not “find semantically similar text.” The target is “find prior reviewed experience that helps resolve or handle this process state.”

Relevant dimensions include:

- same legal question;
- same process branch;
- same unresolved fact;
- same evidence need;
- same exception;
- similar expert correction;
- and compatible claim scope.

## 11.2 Current public implementation

**State:** Implemented and verified as deterministic reference retrieval.

The public runtime:

1. loads reviewed case memories first;
2. excludes the current claim ID;
3. scores candidates through deterministic attributes;
4. fills remaining slots from three static generated historical cases;
5. returns three distinct precedents.

The static references are:

- `HIST-MOULD-014`;
- `HIST-MOULD-022`;
- `HIST-MOULD-009`.

After the flagship is reviewed, the later claim retrieves `DEF-027-E0-DEMO` as its first precedent.

## 11.3 Self-retrieval bug

An earlier retrieval path could return the current claim as a similar case. That creates false confidence and invalidates reuse evidence.

The current public pipeline explicitly excludes:

```text
candidate.claim_id == current_claim_id
```

The backend test and browser proof assert that the later claim does not retrieve itself.

Any future retrieval evaluation must include:

- current-claim exclusion;
- family or near-duplicate exclusion where needed;
- source-group isolation;
- and separate reporting for reviewed memory versus generated reference memory.

## 11.4 Reviewed memory should outrank generated reference

A reviewed case memory should carry:

- expert decision;
- correction operations;
- version;
- sources;
- process path;
- evidence state;
- disagreement status;
- reviewer role;
- and review timestamp.

Generated reference cases should be clearly labeled and receive lower authority. They may support development, but they should not be presented as equivalent to reviewed operational experience.

## 11.5 Limitations of generic similarity

Text similarity can retrieve:

- the same surface vocabulary but the wrong branch;
- the same category but a resolved rather than unresolved fact;
- a near-duplicate generated template;
- or a case whose expert correction is irrelevant.

The retrieval target should be evaluated through **usefulness at a decision**, not only recall of a category label.

## 11.6 Decisive retrieval experiment

For an expert-reviewed set, compare:

- BM25 or lexical similarity;
- dense text similarity;
- canonical-fact similarity;
- process-state similarity;
- graph-edit similarity;
- correction-aware retrieval;
- and hybrid retrieval.

Ask experts:

- Did this case change or confirm the handling decision?
- Did it provide a reusable evidence pattern?
- Was the correction relevant?
- Would the handler have opened it?
- Did it reduce review time or improve the plan?

---

# 12. Expert feedback, reviewed memory, and shared learning

## 12.1 Two different learning products

### One reviewed claim

A single reviewed claim becomes:

```text
Reviewed Case Memory
```

It can immediately support future retrieval because it is a record of what happened in one case.

### Repeated compatible corrections

Repeated corrections may support:

```text
Candidate Knowledge Patch
```

A candidate patch may affect:

- a process node;
- a branch condition;
- evidence ownership;
- evidence applicability;
- process order;
- source interpretation;
- or an allowed alternative.

It must not become shared procedure automatically.

## 12.2 Required promotion gates

A candidate reusable process change should require:

- support from distinct reviewed claims;
- counterexamples;
- source-group separation;
- target-case evaluation;
- protected regression evaluation;
- integrity validation;
- legal or policy authority review where relevant;
- process-owner approval;
- versioned release;
- and rollback target.

A safety exception may use a different promotion threshold only if its authority, severity, scope, and review process were registered in advance.

## 12.3 Current public expert review

**State:** Implemented and verified as a narrow product interaction; generated-reference only as learning evidence.

The expert chooses how to sequence broader building testing:

- **Neutral assessment first**, keeping building-envelope assessment conditional; or
- **Request broader testing now**.

The UI shows the immediate delta in:

- process;
- evidence;
- and next action.

The approved reference correction:

- adds `ventilation_dispute`;
- links use-related evidence to that decision;
- keeps causation unresolved;
- keeps broader building-envelope testing conditional;
- and makes the later claim use v4.

## 12.4 Public promotion is illustrative, not a real governance result

In the v15 public pipeline, support and evaluation values are generated reference values:

```text
support_count: 3
target tests: 6/6
protected regression: 12/12
new version: mould-playbook-v4
rollback: mould-playbook-v3
```

These are not computed through a fresh model or benchmark run during the public review. They are deterministic demonstration data.

The public UX correctly explains the separation between reviewed memory and shared rule, but the backend promotion should not be cited as evidence that the governance method works.

## 12.5 Recurring-condensation and ventilation lesson

The hardened vertical slice withholds a branch for recurring condensation where the landlord alleges ventilation as the cause.

The broad category remains `mould_recurrence`; the answer is not leaked through a special subtype.

A narrow generated-reference trigger was learned:

```text
landlord_alleges_ventilation = true
AND recurring_condensation = true
AND cause_disputed = true
AND ventilation_allegation_relevant = true
AND technical_report_disproves_ventilation = false
AND visual_evidence_conflicts_with_moisture_claim = false
AND heating_emergency = false
```

The operational lesson is not “ventilation is the cause.” It is:

> **Make the allegation an explicit process question and sequence competent evidence before expanding the investigation.**

This distinction matters. The system should preserve the allegation as disputed until evidence supports it.

## 12.6 One correction must not silently change shared knowledge

A one-off correction may reflect:

- a unique fact pattern;
- an individual preference;
- an annotation error;
- a local policy;
- a legal disagreement;
- or an exceptional safety case.

Shared knowledge needs support and counterexamples. The safest default is:

```text
reviewed case saved immediately
candidate rule quarantined
shared playbook unchanged
```

The public demo’s immediate v4 release is a narrative device backed by generated support, not a production precedent.

---

# 13. Evaluation and research findings

This section records questions, setups, results, interpretations, and subsequent decisions. All numerical results below are generated-fixture results unless explicitly stated otherwise.

## 13.1 Original corpus shortcut audit

| Item | Description |
|---|---|
| Question | Does category accuracy measure claim understanding? |
| Setup | 150 generated bilingual claims across three categories |
| Result | Subject-only category accuracy: **95.3%** |
| Interpretation | Category was strongly encoded in surface text; category accuracy was not strong evidence of document reasoning |
| What changed | The project built a harder language/source-disjoint defects vertical slice with neutral or misleading subjects |

## 13.2 Original process-template audit

| Item | Description |
|---|---|
| Question | Does process-node performance measure claim-specific process recovery? |
| Setup | Audit graph skeletons and current nodes in the original corpus |
| Result | One graph skeleton and one intake node per category; all claims in `submitted` state |
| Interpretation | Process recovery largely reduced to category recognition |
| What changed | Later benchmark introduced 28 process paths, 12 current nodes, longitudinal episodes, and negative cases |

## 13.3 Original sparse-feedback experiment

| Item | Description |
|---|---|
| Question | Does nearest-case adaptation improve unseen patterns with 0–10 examples? |
| Setup | Static playbooks, legal-RAG-only, nearest-case reuse, adaptive process agent; 4,800 method–claim observations |
| Result at 10 examples | Subcategory 27.1%, process-node F1 71.6%, checklist F1 94.7%, next action 75.0%, whole-plan exact 2.1%; effectively no improvement from zero examples |
| Interpretation | Retrieval reused outputs but did not reliably induce the controlling rule |
| What changed | The task was narrowed to a withheld branch with explicit contrast and rule-induction methods |

## 13.4 Hardened intake-understanding audit

There are two report snapshots. Keep them separate.

### Deep-recovery report snapshot

| Input | Balanced accuracy |
|---|---:|
| Subject only | 0.500 |
| First sentence only | 0.500 |
| Message bag of words | 0.500 |
| Attachment names only | 0.550 |
| Full message and attachment text | 0.988 |
| Transparent full-package reference | 1.000 |

### Earlier experiment-report snapshot

| Input | Balanced accuracy |
|---|---:|
| Subject only | 0.812 |
| Full observable package | 1.000 |
| Transparent reference | 1.000 |

The difference likely reflects report version, split, or task-definition changes. Do not average or silently choose one. Recover exact manifests and split IDs before publication.

Interpretation: the hardened benchmark substantially reduces the original shortcut, and full package access matters.

## 13.5 Attachment-decisive cases

| Item | Description |
|---|---|
| Question | Do attachments materially change the whole plan? |
| Setup | 35 attachment-decisive initial episodes in one report; message-only versus full package |
| Result | Message only: 0.200 whole-plan constraint match; full observable package: 0.914 |
| Interpretation | The task cannot be solved reliably from the customer narrative alone |
| What changed | Attachment sufficiency, conflicts, misleading names, duplicates, irrelevant files, and evidence ownership became first-class |

## 13.6 Claim-specific process instantiation

| Method | Branch accuracy |
|---|---:|
| Category template | 0.068 |
| Static process library | 0.705 |
| Generated reference | 1.000 |

Interpretation: category alone is not enough once the benchmark includes real branch variation. The static library is a strong baseline and must remain in every evaluation.

## 13.7 Longitudinal updating

The deeper report states:

| Property | Result |
|---|---:|
| Satisfied requests removed | 1.000 |
| Newly required requests added | 1.000 |
| Required branch changes made | 1.000 |
| Obsolete branches retained | 0.000 |
| Correct readiness timing | 1.000 |
| Transition constraints satisfied | 0.977 |
| Future-artifact leaks | 0 |

An earlier simplified report states all transition constraints as 1.000 over 88 transitions.

Interpretation: the longitudinal mechanism is executable, but report drift and the residual mismatch require case-level reconciliation before a definitive claim.

## 13.8 Negative and out-of-scope cases

The hardened scenario set added:

- no current dispute;
- advisory-only;
- hotel;
- owner-occupied;
- wrong jurisdiction;
- duplicate;
- insufficient tenancy/dispute evidence;
- adjacent rent issue after resolved defect.

Interpretation: a safe system must be able to return “not this process,” “insufficient information,” or “no current dispute,” not only choose among positive branches.

## 13.9 Whole-plan and disagreement-aware evaluation

The expert-ready release includes:

- 30 generated constraint targets;
- seven explicit disagreement probes;
- at least one target with multiple valid alternatives;
- typed disagreements:
  - factual;
  - legal;
  - process preference;
  - annotation error.

Interpretation: exact match alone over-penalizes valid alternatives and hides the reason for disagreement.

## 13.10 Sparse adaptation comparison

Methods compared:

- static playbook;
- direct few-shot prediction over canonical facts;
- text-similarity retrieval;
- process-state retrieval;
- graph-edit retrieval;
- contrastive demonstrations;
- structured rule induction;
- small decision tree;
- verified program synthesis;
- prepared LLM rule-proposal contract.

The provider-backed LLM arm was not run.

### Selected generated-fixture method

Verified program synthesis at three examples:

| Metric | Result |
|---|---:|
| Branch accuracy | 1.000 |
| Critical-document recall | 1.000 |
| Confirmatory false activation | 0.000 |
| Development false activation | 0.000 |
| Protected regression | 0.000 |

False activation on development cases:

| Method | False activation |
|---|---:|
| Graph-edit retrieval | 0.500 |
| Contrastive demonstrations | 0.250 |
| Decision tree | 0.625 |
| Verified program synthesis | 0.000 |

Interpretation: methods that fit positive examples can still over-activate on adversarial negatives. Verification and narrow predicates mattered more than expressive complexity.

What changed: verified program synthesis became the selected generated-fixture method, but it was not promoted to the public runtime and has not been validated from genuine expert feedback.

## 13.11 Canonical-fact error propagation

| Fact source | Whole-plan match |
|---|---:|
| Perfect reference facts | 1.000 |
| Deterministic extracted facts | 0.917 |
| Local model-extracted facts | 0.000 |

Highest-impact facts:

1. `heating_emergency`
2. `health_risk`
3. `deadline_status`
4. `landlord_notified`

Interpretation:

> Strong process execution cannot compensate for a weak canonicalizer.

What changed: the research agenda must evaluate claim interpretation separately and report end-to-end versus mechanism-track performance.

## 13.12 Operational back-and-forth simulation

Verified-patch process:

| Metric per journey | Result |
|---|---:|
| Customer-contact rounds | 1.313 |
| Unnecessary requests | 0.000 |
| Critical evidence missed | 0.000 |
| Expert interventions | 0.208 |
| Wrong-ready decisions | 0.000 |

Static category checklist:

```text
9.938 unnecessary requests per journey
```

Interpretation: process-grounded evidence can reduce simulated over-requesting under the generated response schedule.

Boundary: this does not prove real customer-friction or time savings.

## 13.13 Simulated review dry run

Two simulated reviewer profiles completed 60 reviews across 30 items:

| Outcome | Count or value |
|---|---:|
| Approved | 41 |
| Approved with edits | 12 |
| Escalated | 6 |
| Alternative valid plan | 1 |
| Exact decision agreement | 0.567 |
| Unresolved disagreements | 13 |
| Structured edits | 12 |
| Median simulated time | 280 seconds |

Interpretation: the review interface can represent disagreement and correction.

Boundary: simulated reviewers are not experts and do not validate labels, usability, or review time.

## 13.14 Public v20 product gate

| Item | Result |
|---|---:|
| Focused browser checks | 57/57 |
| Backend runs through UI | 2 |
| Console errors | 0 |
| Page errors | 0 |
| Public request failures | 0 |
| 390 px overflow | 0 |
| 320 px overflow | 0 |
| Demo reset | v3 |

Interpretation: the product story is technically demonstrable and responsive.

Boundary: browser correctness does not validate research claims.

## 13.15 Missing confirmatory evidence

Still missing:

- independent Swiss-law review;
- independent claim-process review;
- blind realism study;
- source-isolated naturalistic claims;
- equally informed direct-model baseline on expert targets;
- live provider-backed model results;
- timed expert comparison;
- real customer-contact reduction;
- durable multi-version sequential update study;
- and independent clean-environment reproduction of the current integrated v20 product plus the hardened benchmark.

---

# 14. Do not rediscover

| Attempt or idea | Why it was tried | Result | Lesson | Current decision |
|---|---|---|---|---|
| Category-template process graphs | Fast initial baseline | High apparent process scores in original corpus; branch accuracy collapsed to 0.068 on hardened variation | Category is not a process instance | **Rejected as primary method; retain as baseline** |
| Checklist as independent multi-label prediction | Simple supervised task | Can produce plausible but procedurally irrelevant lists | Evidence applicability depends on reached decisions | **Rejected as CasePath core; retain as baseline** |
| Static category checklist | Operationally simple comparator | 9.938 unnecessary requests per generated journey | Generic lists over-request inactive branches | **Rejected for final product; mandatory baseline** |
| Next-blocker-centric product | Focus attention on immediate action | Hid the complete organizational process and made CasePath look like a next-action tool | Show full graph with current overlay | **Rejected as main UX** |
| Giant process modal | Preserve dashboard while exposing graph | Made the main output feel supplementary and document-like | Graph is the product map | **Abandoned** |
| Report-like result pages | Display every artifact | Users had to reconstruct relationships mentally | One dominant artifact; complexity on demand | **Abandoned** |
| Dense three-column dashboards | Show claim, plan, and checklist together | High information density but weak comprehension | Persistent source + one evolving work pane | **Abandoned for flagship** |
| Expose all agents simultaneously | Demonstrate orchestration | Became architecture theater and persistent clutter | One active specialist; agent recedes after artifact | **Abandoned** |
| Permanent multi-agent rail | Preserve activity history | Competed with graph after process emerged | Collapse completed activity | **Removed in v20** |
| Repeated “Inspect” buttons | Make technical detail accessible | Created control noise and unclear hierarchy | Contextual source/law links; one audit view | **Abandoned** |
| Static safe attachment preview | Avoid exposing raw artifacts | Broke the operational claim experience | Render actual generated PDF/image/email | **Abandoned** |
| Browser-local corrections presented as learning | Fast front-end demonstration | No durable or inspectable organizational update | Server review + memory + versioned candidate | **Rejected** |
| Text-similarity retrieval | Simple precedent baseline | Matches vocabulary rather than controlling process state | Evaluate decision usefulness | **Insufficient; retain baseline** |
| Nearest-case retrieval | Reuse reviewed output | 0.556 branch accuracy on withheld pattern | Reuse does not induce a general rule | **Insufficient** |
| Exact process-state retrieval | Match structured state | 0.333 branch accuracy | State equality is brittle and may miss controlling literals | **Insufficient** |
| Graph-edit retrieval | Reuse prior correction | Fit positives but 0.500 dev false activation | Edit similarity does not guarantee trigger validity | **Rejected for promotion** |
| Contrastive demonstrations | Highlight positive/negative differences | 0.250 dev false activation | Contrasts help but need formal support checks | **Research baseline, not selected** |
| Small decision tree | Transparent induction | 0.625 dev false activation | Transparency is not enough without semantic constraints | **Rejected for promotion** |
| Structured rule induction | Learn explicit trigger | Improved withheld branch in generated fixture | Needs counterexamples and verification | **Useful research direction; not deployed** |
| Verified program synthesis | Find narrow rule satisfying constraints | Perfect generated challenge metrics at three examples | Verification controls false activation in the tested fixture | **Selected synthetic research method; not operationally validated** |
| Provider-backed LLM rule proposal | Test flexible induction | Contract prepared, call not run | Do not invent provider results | **Planned experiment** |
| Subject-line classification | Cheap intake model | 95.3% on original corpus | Benchmark leaked category through surface form | **Rejected as evidence of understanding** |
| One graph skeleton per category | Easy ground-truth generation | Made process recovery nearly predetermined | Vary branch facts and current nodes inside category | **Rejected benchmark design** |
| Only positive in-scope cases | Simplify generation | Scope gate could never fail correctly | Add negatives and insufficient cases | **Rejected benchmark design** |
| Intake-only snapshots | Simplify labels | Could not test evidence arrival or branch reversal | Use journeys and episodes | **Rejected benchmark design** |
| Generated-reference exact match as “expert truth” | Needed labels quickly | No domain validity | Label explicitly and run expert review | **Rejected wording and claim** |
| Hard-coded generated regression results as production learning | Make lifecycle visible | Useful demo, not real governance evidence | Keep narrative but label generated reference | **Prototype only** |
| LangChain/Nemotron branch as current product claim | Stronger agentic architecture | Source exists historically, live call unverified, not in current master | Architecture and deployment truth must be separated | **Do not claim current use; recover only for deliberate experiment** |
| Repeated Render deployment during UX design | Immediate public feedback | Created regressions, SHA confusion, and sideways iteration | Freeze locally, validate, deploy once | **Rejected workflow** |
| Layering new UI patches indefinitely | Avoid rewriting stable core | v20 works but now has v16–v20 interdependent layers | Consolidate only after the milestone, with visual parity tests | **Current technical debt; do not add v21 patch casually** |
| Composite “usefulness score” | Summarize many outcomes | Can hide safety failures and target drift | Report dimensions and severe failures separately | **Do not use as sole headline** |
| Generic process-mining architecture before data feasibility | Ambitious reusable stack | Risked months of infrastructure before task validation | Validate one bounded vertical slice first | **Deferred** |

---

# 15. UX journey and design history

## 15.1 Repeated failure mode

> **Backend sophistication increased while practical product usefulness remained hidden behind report-like interfaces.**

This was the dominant product failure across several releases.

The system accumulated:

- process graphs;
- evidence relationships;
- legal sources;
- agent traces;
- counts;
- precedent cards;
- audit metadata;
- review controls;
- and knowledge-update summaries.

The UI displayed them simultaneously. The user had to infer how they related.

## 15.2 Desired flagship journey

```text
Customer submission
→ Agents working
→ Process emerges
→ Evidence attaches to process
→ Relevant experience appears
→ Expert edits reasoning
→ Knowledge is saved
→ Next claim benefits
```

This is a guided product sequence, not a navigation taxonomy.

## 15.3 Design principles now accepted

- The original claim remains visible.
- Actual generated PDFs, images, and emails are inspectable.
- Agent activity corresponds to backend events.
- One active specialist is shown at a time.
- Agent activity recedes after producing an artifact.
- The process graph is the hero artifact.
- The graph is not hidden in a modal.
- Evidence status is attached to decisions.
- Law appears at the decision it shapes.
- Prior cases appear where useful.
- The complete document list is derived and secondary.
- Expert review happens beside the graph.
- Learning resolves into a few meaningful outcomes.
- The final moment is a later claim, not a release report.
- Technical audit is available but hidden by default.
- One dominant idea appears at a time.
- Product copy uses task language rather than research-report language.

## 15.4 Important negative examples

Archived negative examples include:

- `desktop-review.png`: dense three-column review dashboard;
- `desktop-edited.png`: corrected but still dashboard-like;
- earlier public screenshots with “Safe generated preview” instead of actual source artifacts;
- v17/v18 report pages showing summaries, counts, and graph simultaneously;
- giant graph modal;
- permanent team rail;
- loading page with a mostly blank workspace.

These should remain regression references. Do not delete them from the research archive.

## 15.5 Current v20 interaction model

The current v20 frontend is a focused layer over older runtime code.

Start:

```text
left: generated customer submission
right: “What should CasePath do with this claim?”
action: “Analyse claim”
```

Analysis:

- one current specialist;
- source claim remains visible;
- actual event rows appear.

Process moment:

- orchestrator and progress chrome are hidden;
- graph fills the right pane;
- current and blocked decisions are explicit.

Evidence and experience:

- node-level status;
- focused inspector;
- contextual prior cases.

Ready moment:

- graph remains primary;
- document needs open as a temporary derived sheet.

Review:

- graph plus one evidence-order decision and its delta.

Learning:

- reviewed case saved;
- expert correction captured;
- shared playbook change.

Later claim:

- working trace recedes;
- before/after becomes primary.

## 15.6 Current UX technical debt

- v20 depends on layers from v16, v17, v18, and v19.
- Behavior is controlled through DOM observation and post-render enhancement.
- CSS hides legacy components rather than removing all old generation code.
- Release markers are set by several scripts.
- `window.CASEPATH_EXPERIENCE_RELEASE` is mutable and may be overwritten by an older layer.
- The current QA wrapper on master is not the exact wrapper used by the live passing canonical QA.
- The DOM contract is fragile: internal class names such as `needed` versus `still-needed` have already broken QA.
- Accessibility is checked only at a basic level.
- No first-time-user comprehension study has been run.

Do not add another additive UX layer unless a critical bug cannot be fixed within v20. The next consolidation should reduce layers, not add `live-v21-*`.

---

# 16. Deployment and release history

## 16.1 Current deployment architecture

```text
GitHub repository
├── casepath/       → Render static site
├── casepath-api/   → Render Python web service
└── casepath-qa/    → Render Node/Playwright evidence service
```

### Frontend

```text
Service: casepath-swiss-claim-lab
Type: Render static site
Branch: master
Publish path: casepath
URL: https://casepath-swiss-claim-lab.onrender.com/
```

### API

```text
Service: casepath-agentic-api
Type: Render Python web service
Branch: master
Build: bash casepath-api/render-build.sh
Start: bash casepath-api/start.sh
URL: https://casepath-agentic-api.onrender.com/
Region: Frankfurt
Plan: free
```

### Canonical QA

```text
Service: casepath-guided-canonical-qa
Type: Render Node web service
Build: install dependencies and Chromium, run Playwright, publish evidence directory
URL: https://casepath-guided-canonical-qa.onrender.com/
```

## 16.2 Persistence

The API stores:

- runs;
- events;
- reviews;
- memories;
- candidates.

Storage is SQLite at:

```text
CASEPATH_DB_PATH
default: /tmp/casepath-useful-demo/casepath.db
```

On Render, `/tmp` is ephemeral. This is suitable only for a resettable demonstration.

**State:** Implemented but not durable.

A real pilot needs:

- PostgreSQL or another approved durable store;
- migrations;
- transactional versioning;
- tenant/data separation;
- retention policy;
- backup and restore;
- audit immutability;
- and explicit reset semantics.

## 16.3 Environment variables

Current runtime:

| Variable | Purpose |
|---|---|
| `PORT` | Render or local Uvicorn port |
| `CASEPATH_DB_PATH` | SQLite database path |
| frontend query `api` | Override API URL during local/QA use |
| `BASE_URL` | Browser QA target |
| `API_URL` | Browser QA API target |

Historical live-model prototype:

| Variable | Purpose |
|---|---|
| OpenRouter credential, name varied by release | Authorized live model call |
| model/provider config | Select Nemotron and restrict provider |

Do not include credentials in source, logs, screenshots, manifests, or handoff documents.

## 16.4 Release-marker inconsistency

Current inspected markers:

| Location | Marker |
|---|---:|
| `casepath/index.html` | 20.0.0 |
| public API | 15.0.0 |
| `casepath/release.json` | 12.0.2 |
| `casepath/source-manifest.json` | 10.0.0 |
| older JS layers | 16–19 |

The HTML and API health endpoints are the current runtime truth. The JSON release and source-manifest files are stale. Repair them before another release claim.

## 16.5 Preferred release workflow

```text
local iteration
→ visual acceptance screenshots
→ full local uninterrupted demo
→ deterministic and browser tests
→ freeze candidate commit
→ deploy once
→ deployment-only fixes
→ retained production evidence
```

Do not redesign while debugging deployment.

## 16.6 Render troubleshooting

### Static frontend shows stale content

- Confirm service branch and deploy SHA.
- Confirm `publishPath=casepath`.
- Trigger a cache-cleared deploy only after verifying the source commit.
- Inspect HTML release meta and loaded asset URLs.
- Do not trust a text-only crawler for the JS-rendered state.

### API build succeeds but behavior is old

- Confirm `app.py` imports `pipeline_v15`, not legacy `pipeline`.
- Check live `/healthz` and `/deployment-health`.
- Compare live deploy SHA with the source SHA.
- Remember that v20 was frontend-only; API SHA lag may be intentional but must be documented.

### QA build fails

- Inspect selector drift.
- Do not weaken an assertion just to obtain a pass.
- First determine whether the product regressed or the QA assumption was wrong.
- Preserve a failure screenshot and exact locator.
- Run against production, not a preview, for final acceptance.
- Close browser context before resetting API state to avoid late polling 404s.

### No open port

- Confirm the Render start command uses `$PORT`.
- For QA evidence service, use an HTTP server over the generated output directory.
- For API, use `bash casepath-api/start.sh`.

### Free-tier cold start

- Use long navigation and API timeouts.
- Separate cold-start latency from pipeline latency.
- Do not script fake progress to hide a sleeping service.
- Warm the service before a recorded stakeholder demonstration if permitted.

## 16.7 Release-history lesson

The project has many versioned branches because deployment and redesign were interleaved. This made “latest” ambiguous.

Before future work:

- tag the product baseline;
- distinguish product commit from QA-only commit;
- distinguish benchmark release from demo release;
- keep one changelog;
- and record exact SHAs for frontend, API, QA, and benchmark.

---

# 17. Model and cost constraints

## 17.1 Historical reference models

Two model IDs appear in historical artifacts:

```text
nvidia/nemotron-3-super-120b-a12b:free
nvidia/nemotron-3-ultra-550b-a55b:free
```

Do not assume they are aliases or equally available. Choose and validate one model for any new live experiment.

## 17.2 OpenRouter design

The historical integration used:

- OpenRouter Chat Completions through `ChatOpenAI`;
- NVIDIA-only routing;
- fallback disabled;
- data collection denied;
- structured Pydantic output;
- temperature 0;
- no automatic retry;
- explicit reasoning configuration;
- and source/output validation.

This is not in the current public runtime.

## 17.3 Historical free-call budget

A prior budget planned approximately 50 calls:

- 3 provider/auth/schema smoke;
- 8 representative English/German;
- 6 adversarial attachment-dependent;
- 5 longitudinal/correction-sensitive;
- 5 post-fix regression;
- 3 deployed acceptance;
- 20 reserve.

The release record stated zero calls had been used because no authorized credential was available.

This budget is historical. OpenRouter availability, model price, and free quotas can change. Verify current provider terms before any run.

## 17.4 Cost-control rules

1. Run schema, unit, deterministic conformance, leakage, and browser tests first.
2. Cache by:
   - claim version;
   - observable-input hash;
   - model;
   - provider;
   - prompt version;
   - schema version;
   - agent role.
3. Do not spend live calls on UI debugging.
4. Use generated canonical states for mechanism tests.
5. Reserve calls for questions that deterministic fixtures cannot answer.
6. Store complete secret-stripped request and response envelopes.
7. Report provider failures and parse failures; do not silently fall back and call the result “Nemotron.”
8. Never make a live-model performance claim from a handful of demonstration calls.
9. Do not use a visitor-supplied secret in logs or persistent browser storage.
10. Current public demo must continue to work without a model credential.

## 17.5 What a live call should test first

The first authorized call should test one bounded contract:

```text
observable flagship package
→ source-linked canonical claim state
```

The deterministic pipeline should then build graph, checklist, and verification from that state.

Do not begin with free-form end-to-end graph generation. Canonical-state quality is already known to dominate downstream performance.



# 18. Repository map

## 18.1 Repository-level warning

`KumarNavish/KumarNavish.github.io` is not a dedicated CasePath repository. Its root contains unrelated portfolio infrastructure. Do not run root-level commands and assume they validate CasePath.

Open the following CasePath paths directly.

## 18.2 Frontend

| Path | State | Why a new agent opens it |
|---|---|---|
| [`casepath/index.html`](https://github.com/KumarNavish/KumarNavish.github.io/blob/master/casepath/index.html) | Current | Static entry point, initial claim shell, source viewer, work pane, audit and precedent dialogs, loaded asset order |
| [`casepath/assets/live-v16.js`](https://github.com/KumarNavish/KumarNavish.github.io/blob/master/casepath/assets/live-v16.js) | Current core runtime | Main client state machine, API calls, claim rendering, process rendering, review, knowledge, and later-claim flow |
| [`casepath/assets/live-v16.css`](https://github.com/KumarNavish/KumarNavish.github.io/blob/master/casepath/assets/live-v16.css) | Current core style | Base layout, graph, inspector, review, knowledge, source viewer, responsive rules |
| `casepath/assets/live-v16-stability.js` | Current support | Guards runtime stability around the v16 core |
| [`casepath/assets/live-v17.js`](https://github.com/KumarNavish/KumarNavish.github.io/blob/master/casepath/assets/live-v17.js) | Current enhancement | Adds process continuity, legal mapping, evidence chains, derived checklist, review and reuse enhancements |
| `casepath/assets/live-v17-continuity.css` | Current enhancement | Styles the graph continuity and v17 additions |
| `casepath/assets/live-v18.js` | Current enhancement | Additional guided-experience behavior |
| `casepath/assets/live-v18.css` | Current enhancement | v18 presentation layer |
| `casepath/assets/live-v18-handoff.js` | Current enhancement | Event-backed handoff and artifact presentation |
| `casepath/assets/live-v18-insertion-guard.js` | Current guard | Prevents duplicate asynchronous component insertion and coalesces some run reads |
| `casepath/assets/live-v18-law-normalize.js` | Current support | Normalizes law disclosure behavior |
| `casepath/assets/live-v19-active-stage.js` | Current enhancement | Active-stage and artifact relationship enhancements |
| `casepath/assets/live-v19.css` | Current enhancement | Team rail, process law/evidence signals, review preview, support meter |
| `casepath/assets/live-v19-runtime-stability.js` | Current support | Runtime stabilization |
| [`casepath/assets/live-v20-focus.js`](https://github.com/KumarNavish/KumarNavish.github.io/blob/master/casepath/assets/live-v20-focus.js) | Current product focus layer | Turns the layered runtime into the graph-first, one-artifact-at-a-time v20 experience |
| [`casepath/assets/live-v20-focus.css`](https://github.com/KumarNavish/KumarNavish.github.io/blob/master/casepath/assets/live-v20-focus.css) | Current product focus layer | Hides report framing and agent chrome, creates the focused two-pane journey |
| [`casepath/release.json`](https://github.com/KumarNavish/KumarNavish.github.io/blob/master/casepath/release.json) | **Stale** | Historical release metadata; currently says 12.0.2 and must not be treated as v20 truth |
| [`casepath/source-manifest.json`](https://github.com/KumarNavish/KumarNavish.github.io/blob/master/casepath/source-manifest.json) | **Stale** | Historical v10 manifest; useful for provenance but not current tree integrity |
| `casepath/_headers` | Current deployment support | Static-site caching and headers |
| `casepath/README.md` | Historical/minimal | Not a complete current handoff |

### Frontend modification rule

Before changing the frontend:

1. identify which layer currently owns the behavior;
2. avoid duplicating a behavior already added by a later layer;
3. capture current screenshots;
4. run the focused browser journey;
5. prefer deleting or consolidating code over adding another override layer.

## 18.3 Current API and backend

| Path | State | Why open it |
|---|---|---|
| [`casepath-api/casepath_api/app.py`](https://github.com/KumarNavish/KumarNavish.github.io/blob/master/casepath-api/casepath_api/app.py) | Current deployed API | Routes, CORS, demo metadata, source-artifact endpoints, run/review/knowledge/reset API |
| [`casepath-api/casepath_api/pipeline_v15.py`](https://github.com/KumarNavish/KumarNavish.github.io/blob/master/casepath-api/casepath_api/pipeline_v15.py) | **Authoritative deployed pipeline** | Complete deterministic reference lifecycle, facts, legal context, graph, evidence, retrieval, verification, review, memory, candidate, and later proof |
| [`casepath-api/casepath_api/data.py`](https://github.com/KumarNavish/KumarNavish.github.io/blob/master/casepath-api/casepath_api/data.py) | Current public data | Exact two claims, nine artifacts, static law sources, static historical cases |
| [`casepath-api/casepath_api/storage.py`](https://github.com/KumarNavish/KumarNavish.github.io/blob/master/casepath-api/casepath_api/storage.py) | Current demo persistence | SQLite schema and CRUD for runs, events, reviews, memories, and candidates |
| [`casepath-api/casepath_api/pipeline.py`](https://github.com/KumarNavish/KumarNavish.github.io/blob/master/casepath-api/casepath_api/pipeline.py) | **Legacy** | Earlier pipeline retained in tree; do not edit expecting deployed behavior |
| [`casepath-api/generate_artifacts.py`](https://github.com/KumarNavish/KumarNavish.github.io/blob/master/casepath-api/generate_artifacts.py) | Current build generator | Produces lease, timeline, receipt, emails, and initial images |
| `casepath-api/replace_photographic_evidence.py` | Current build step | Replaces procedural images with licensed checksum-bound photographs |
| `casepath-api/prepare_runtime_v12.py` | Historical support | Earlier runtime-preparation path; verify usage before changing |
| [`casepath-api/render-build.sh`](https://github.com/KumarNavish/KumarNavish.github.io/blob/master/casepath-api/render-build.sh) | Current Render build | Installs, generates artifacts, replaces photos, checks hashes, compiles, and runs direct API smoke |
| `casepath-api/start.sh` | Current start | Launches Uvicorn on `$PORT` |
| [`casepath-api/requirements.txt`](https://github.com/KumarNavish/KumarNavish.github.io/blob/master/casepath-api/requirements.txt) | Current | Exact API dependencies; absence of LangChain is evidence that current runtime is not model-driven |
| `casepath-api/artifacts/` | Generated/build artifacts | Public source documents and attribution |

## 18.4 Tests and browser QA

| Path | State | Why open it |
|---|---|---|
| [`casepath-api/tests/test_pipeline.py`](https://github.com/KumarNavish/KumarNavish.github.io/blob/master/casepath-api/tests/test_pipeline.py) | **Misaligned legacy test** | Reveals old invariants, but imports `pipeline.py`, not deployed `pipeline_v15.py` |
| [`casepath-qa/browser-focused-v20.mjs`](https://github.com/KumarNavish/KumarNavish.github.io/blob/master/casepath-qa/browser-focused-v20.mjs) | Current desired product gate, **brittle on master** | Full claim-to-reuse Playwright journey and visual checks |
| `casepath-qa/browser-guided-v13-smoke.mjs` | Current wrapper on product commit | Imports the focused v20 gate; the live canonical QA uses a patched variant |
| `casepath-qa/browser-guided-v19-final.mjs.part*` | Historical QA | v19 production gate source segments |
| `casepath-qa/generate-visual-story.py.part*` | Historical visual artifact generator | Standalone GIF generator source |
| `casepath-qa/reset-demo-state.mjs` | Current support | Reset public demo state |
| `casepath-qa/check-photographic-evidence.mjs` | Historical/current support | Verifies public photo evidence |
| `casepath-qa/browser-public.mjs`, `check-public.mjs` | Historical gates | Earlier public checks; do not treat as v20 acceptance |
| `casepath-qa/package.json` | Current QA dependencies | Playwright and Node setup |

### Known focused-QA defects on current product commit

`browser-focused-v20.mjs` currently contains assumptions that differ from the passing canonical service:

- selector uses `data-kind="still-needed"` while the generated group kind is `needed`;
- one assertion hard-codes that the first selected document returns to `causation`;
- release check relies on mutable `window.CASEPATH_EXPERIENCE_RELEASE`.

The canonical QA service passed after these assumptions were patched in a QA-only commit. Merge a clean corrected gate into the product branch before claiming local reproducibility.

## 18.5 Deployment configuration

There is no single current infrastructure-as-code file that defines all live services. Render is configured through the service dashboard.

Record externally:

- service IDs;
- service types;
- branches;
- build commands;
- start commands;
- publish paths;
- regions;
- plans;
- environment variables;
- health endpoints;
- and last accepted SHAs.

Do not infer configuration from old GitHub workflows. Historical v10 installer and verification workflows existed on older branches but are not authoritative for v20.

## 18.6 Research benchmark release

The hardened defects benchmark is not in the current default branch. The important archived structure is:

```text
CasePath_Defects_Expert_Ready_Agent/
├── benchmark/
│   ├── manifest.json
│   ├── packages/
│   ├── bundles/
│   ├── ground_truth/
│   ├── reference_plans/
│   └── expert_review/
├── casepath_agent/
│   ├── benchmark.py
│   ├── process.py
│   ├── adaptation.py
│   ├── adaptation_methods.py
│   ├── interaction.py
│   ├── error_propagation.py
│   ├── review.py
│   └── api.py
├── challenge/
├── experiments/
├── expert_pilot/
├── knowledge/
├── reports/
├── schemas/
├── scripts/
│   ├── run_all.py
│   ├── bootstrap_and_verify.sh
│   └── release_manifest.py
├── tests/
├── ui/
└── requirements-lock.txt
```

Why open it:

- it contains the actual research benchmark, methods, reports, and reproducibility tooling;
- it is the source for most scientific findings in this handoff;
- and it prevents rebuilding experiments from product-demo code.

Before use, verify archive checksums and ensure no absolute `/mnt/data` dependency remains.

## 18.7 Historical model-driven sources

Archived files such as:

```text
casepath_agent/langchain_agents.py
casepath_agent/model_profiles.py
casepath_agent/schemas.py
casepath_agent/storage.py
prompts/
```

represent the LangChain/Nemotron architecture generation. They are not part of current master. Recover them only when the next milestone explicitly requires a live model arm.

---

# 19. Canonical contracts and compact examples

> **Schema-location warning:** the current default branch does not contain the full 47-schema hardened benchmark release. The deployed public runtime expresses contracts directly in Python dictionaries and constructors. The authoritative research schemas live in the archived `CasePath_Defects_Expert_Ready_Agent/schemas/` release and must be checksum-recovered before an experiment. Do not invent a new schema set merely because the archive is not mounted locally.

These examples are representative. The exact source of truth should be versioned schema files, not this prose.

## 19.1 Observable claim

```json
{
  "claim_id": "DEF-027-E0-DEMO",
  "received_at": "2026-08-01T09:10:00+02:00",
  "language": "en",
  "message": {
    "subject": "Recurring mould in bedroom",
    "body": "The mould returned after cleaning. The landlord says ventilation is the cause..."
  },
  "artifacts": [
    {
      "artifact_id": "art_lease",
      "filename": "lease-agreement.pdf",
      "media_type": "application/pdf",
      "page_count": 6,
      "sha256": "..."
    }
  ]
}
```

Invariant: no process, category, expected fact, or answer is embedded.

## 19.2 Canonical claim state

```json
{
  "claim_id": "DEF-027-E0-DEMO",
  "facts": [
    {
      "fact_id": "fact_cause",
      "label": "Technical cause",
      "value": null,
      "state": "unknown",
      "confidence": 1.0,
      "controls_process": true,
      "source_refs": [
        {
          "artifact_id": "art_management_reply",
          "page": 1,
          "excerpt": "We consider insufficient ventilation the likely cause.",
          "agent": "Claim Understanding Agent"
        }
      ]
    }
  ],
  "conflicts": [
    {
      "fact_id": "fact_first_observed_date",
      "values": ["2026-03-12", "2026-03-20"]
    }
  ]
}
```

## 19.3 Process node

```json
{
  "node_id": "causation",
  "title": "Causation assessment",
  "question": "What caused the recurring mould?",
  "kind": "decision",
  "state": "current",
  "answer": "Unresolved",
  "why": "Responsibility and remedy depend on the likely cause.",
  "fact_ids": ["fact_cause", "fact_ventilation_allegation"],
  "legal_source_ids": ["fedlex_or_256"],
  "evidence_requirement_ids": [
    "technical_assessment",
    "moisture_measurements",
    "building_envelope"
  ],
  "branches": [
    {"answer": "building_defect", "target": "responsibility"},
    {"answer": "tenant_use", "target": "responsibility"},
    {"answer": "mixed_cause", "target": "responsibility"},
    {"answer": "insufficient_evidence", "target": "evidence_gap"}
  ]
}
```

## 19.4 Process graph

```json
{
  "graph_id": "mould-playbook-v3:DEF-027-E0-DEMO",
  "version": "mould-playbook-v3",
  "current_node": "causation",
  "main_spine": [
    "intake",
    "scope",
    "dispute",
    "urgency",
    "notification",
    "defect",
    "causation",
    "responsibility",
    "remedy",
    "escalation",
    "resolution"
  ],
  "nodes": [],
  "edges": []
}
```

## 19.5 Evidence item

```json
{
  "item_id": "technical_assessment",
  "title": "Independent technical assessment",
  "node_id": "causation",
  "fact_id": "fact_cause",
  "fact_label": "Likely technical cause",
  "why": "Photos establish visible mould but not its cause.",
  "status": "missing",
  "required_level": "competent_independent_assessment",
  "alternatives": [
    "specialist moisture report",
    "equivalent qualified inspection"
  ],
  "legal_source_ids": ["fedlex_or_256"],
  "artifact_ids": [],
  "applies_when": "cause remains unresolved",
  "current_path": true
}
```

## 19.6 Document requirement

A document requirement is a user-facing projection of one or more evidence items:

```json
{
  "document_type": "technical_assessment",
  "label": "Independent technical assessment",
  "status": "still_needed",
  "required_for": {
    "node_id": "causation",
    "fact_id": "fact_cause"
  },
  "reason": "Needed to distinguish building, use-related, mixed, or unresolved cause.",
  "accepted_alternatives": ["qualified moisture report"],
  "do_not_request_if": ["equivalent competent report already sufficient"]
}
```

## 19.7 Reviewed case memory

```json
{
  "memory_id": "memory_...",
  "claim_id": "DEF-027-E0-DEMO",
  "review_status": "expert_approved_generated_case",
  "reviewed_process_version": "mould-playbook-v3",
  "facts": [],
  "process_path": [],
  "evidence_state": [],
  "expert_corrections": [
    {
      "operation": "replace",
      "pointer": "/checklist/building_envelope/status",
      "old": "missing",
      "new": "conditional",
      "reason": "Use one neutral assessment first."
    }
  ],
  "source_artifact_hashes": [],
  "created_at": "..."
}
```

For a real expert pilot, the reviewer identity, role, authority, disagreement, and scope version must be explicit.

## 19.8 Expert correction

```json
{
  "correction_id": "corr_...",
  "run_id": "run_...",
  "claim_id": "DEF-027-E0-DEMO",
  "decision": "approve_with_edit",
  "operations": [
    {
      "component": "evidence_requirement",
      "operation": "replace",
      "pointer": "/items/building_envelope/status",
      "old_value": "missing",
      "new_value": "conditional",
      "reason": "Broader testing follows only if the neutral assessment cannot distinguish cause.",
      "confidence": 0.93
    }
  ],
  "reviewer_type": "qualified_human_or_simulated_must_be_explicit",
  "created_at": "..."
}
```

## 19.9 Candidate knowledge patch

```json
{
  "candidate_id": "candidate_ventilation_sequence_v1",
  "status": "quarantined",
  "scope": "CH:tenant-law:mould-recurrence",
  "from_version": "mould-playbook-v3",
  "proposed_version": "mould-playbook-v4",
  "change": {
    "add_node": "ventilation_dispute",
    "change_evidence_ownership": true,
    "make_building_envelope_conditional": true
  },
  "support": {
    "distinct_reviewed_claims": 1,
    "required": 3
  },
  "evaluation": {
    "target_manifest": null,
    "protected_manifest": null,
    "status": "not_run"
  },
  "approvals": {
    "process_owner": "pending",
    "legal": "pending"
  },
  "rollback_target": "mould-playbook-v3"
}
```

This is the correct default after one genuine reviewed case. The public demo’s generated candidate uses prefilled support and evaluation values for narrative purposes.

---

# 20. Precise current-state table

| Capability | State | Evidence | Main limitation | Next action |
|---|---|---|---|---|
| Original 150-claim generation | **Prototype / generated-reference only** | 150 claims, 2,251 files, reproducibility report | Shortcut-heavy, low attachment density, no expert approval, separate from current repo | Preserve as historical baseline; do not extend |
| Hardened defects generation | **Prototype / generated-reference only** | 48 journeys, 136 episodes, 1,148 attachments | Archived outside current default branch; generated labels | Recover and checksum-verify release |
| Public flagship artifact generation | **Implemented and verified** | Build script, six-page lease, PDFs/emails/photos | Visible generated markers; only two claims; no blind realism study | Rerender one flagship to leakage-clean realism standard |
| Claim browsing | **Planned / not in v20 flagship** | Older corpus UI generations | Current product intentionally exposes two claims only | Do not rebuild broad inbox before flagship validation |
| Attachment rendering | **Implemented and verified** | Six-page PDF, zoom, extraction separation, source photo | Generated and highly curated | Add realism and source-level expert review |
| Claim interpretation | **Prototype / generated-reference only** | Source-linked facts and conflicts in v15 | Deterministic predefined facts; no current model arm | Reintroduce bounded canonicalizer experiment |
| Legal query formulation | **Prototype / generated-reference only** | Five questions in v15 | Handcrafted | Evaluate model question quality separately |
| Legal RAG | **Prototype / generated-reference only** | Static official-source registry and node links | Not live retrieval; operational interpretation unapproved | Build versioned official-source retrieval and expert review |
| Process discovery | **Prototype / generated-reference only** | 11-node graph, later v4 variation | Handcrafted two-case graph; no general inference | Run adjudicated graph-instantiation experiment |
| Process graph product UI | **Implemented and verified** | v20 graph-first browser gate | Layered DOM-enhancement technical debt | Preserve until milestone; then consolidate |
| Checklist generation | **Implemented and verified for reference cases** | 20 node/fact/reason-linked items | Handcrafted evidence model | Compare against direct predictor on expert targets |
| Historical retrieval | **Implemented and verified for reference cases** | Three precedents, self-exclusion, reviewed memory first | Static deterministic score and generated cases | Evaluate correction-aware retrieval |
| Expert review UI | **Implemented and verified narrowly** | One graph-adjacent evidence-order choice | Not a general graph editor; no qualified expert session | Run real review on one flagship |
| General typed correction system | **Implemented in archived expert-ready release** | Typed operation descriptions and review API artifacts | Not integrated into current v20 master | Recover only for expert-pilot milestone |
| Reviewed case memory | **Implemented and verified in demo** | Memory written and reused by later claim | Ephemeral SQLite; generated review | Move to durable store and real reviewer |
| Shared knowledge evolution | **Prototype / generated-reference only** | v3→v4 demo, rollback field | Hard-coded support/tests; no fresh regression | Connect candidate to actual evaluation manifests |
| Verified program synthesis | **Prototype / generated-reference only** | Perfect 3-example challenge result | One synthetic withheld branch; archived | Replicate on expert-reviewed corrections |
| Orchestrator swapping | **Planned with historical prototype** | Shared contract design and archived LangChain suite | No current interface in master | Add explicit adapter boundary only when model arm begins |
| Live Nemotron | **Not implemented in current runtime** | Historical OpenRouter source and call budget | No current dependency, no verified call | One authorized canonicalizer smoke after deterministic gates |
| Model/provider abstraction | **Historical prototype / planned** | Archived profiles and LangChain suite | Not in current public code | Recover selectively, not wholesale |
| Public UI | **Implemented and verified** | 57/57 focused browser checks | Comprehension not user-tested; layered v16–v20 | Run silent first-time-viewer test |
| Browser QA | **Implemented but source misaligned** | Live canonical service passed | Product master gate contains stale assumptions | Merge corrected gate and rerun locally |
| Backend unit tests | **Implemented but not aligned** | `tests/test_pipeline.py` | Imports legacy `pipeline.py`, not v15 | Rewrite tests against deployed pipeline |
| Persistence | **Implemented but not durable** | SQLite tables | `/tmp` on Render | Add PostgreSQL before real pilot |
| Deployment | **Implemented and live** | Frontend, API, QA services | Different SHAs/releases, stale manifests | Create one release manifest across services |
| Benchmark validity | **Not established** | Strong internal generated tests | No qualified expert or source-isolated transfer | Expert annotation and realism study |
| Legal validity | **Not established** | Official sources linked | Operational translations unreviewed | Qualified Swiss tenant-law review |
| Expert validation | **Not performed on current flagship** | Simulated dry run only | No real reviewers | Obtain at least two independent reviews and adjudication |
| Operational benefit | **Not established** | Generated interaction simulation | No real handlers or customers | Timed matched workflow study |
| Real-claim use | **Not approved** | Safety statements | Privacy, legal, security, institutional approvals absent | Do not ingest real data |

---

# 21. Irreducible research questions

Engineering can make CasePath faster or prettier. The questions below require experiments.

## 21.1 Can a system infer useful claim-specific handling graphs from limited traces?

### Decisive experiment

- Obtain expert-reviewed claim families with observable packages.
- Hide the reviewed graph.
- Compare:
  - category template;
  - deterministic library instantiation;
  - direct graph predictor;
  - process-aware model;
  - retrieval;
  - and human baseline.
- Score:
  - constraint validity;
  - current-node accuracy;
  - critical branch recall;
  - accepted alternative coverage;
  - and review edit distance.
- Use source-group-isolated test families.

## 21.2 Does explicit process reasoning improve evidence requirements?

### Decisive experiment

Use the same model, context, training data, and budget.

Compare:

- direct checklist prediction;
- graph-aware direct prediction;
- process-bottleneck prediction;
- process oracle;
- and static checklist.

Measure:

- critical evidence recall;
- unnecessary requests;
- already-present repeat requests;
- conditional-evidence errors;
- whole-plan constraint match;
- and expert review time.

## 21.3 How should multiple valid process graphs be evaluated?

### Decisive experiment

- Two or more qualified handlers independently annotate the same cases.
- Adjudicate factual versus legal versus preference disagreements.
- Construct set-valued or constraint-based targets.
- Compare exact-match, graph edit distance, trace equivalence, and operational outcome equivalence.
- Determine which metric best predicts expert acceptance.

## 21.4 How much expert feedback is needed to learn reusable process knowledge?

### Decisive experiment

- Predefine withheld process patterns.
- Collect genuine reviewed corrections sequentially.
- At budgets 1, 2, 3, 5, and 10:
  - propose candidate rules;
  - evaluate target cases;
  - evaluate adversarial negatives;
  - replay protected archive;
  - record expert minutes.
- Compare verified program synthesis, rule induction, retrieval, direct prompting, and manual playbook editing.

## 21.5 How do we avoid corrupting valid old playbooks?

### Decisive experiment

Run a prequential sequence of corrections across several claim families.

For every proposal:

- record support;
- run protected replay;
- measure worst-family regression;
- preserve rollback;
- simulate a bad correction;
- and verify rejection and recovery.

Report severe failures separately from average accuracy.

## 21.6 How much does canonical-state error dominate downstream performance?

### Decisive experiment

Use:

- adjudicated canonical states;
- model-generated states;
- deterministic states;
- controlled perturbations;
- and provenance ablations.

Measure component and whole-plan degradation, abstention, and unsafe branch activation.

## 21.7 Does generated benchmark performance transfer to real claims?

### Decisive experiment

- Create a legally approved source-isolated evaluation panel.
- Freeze schema and method before access.
- Compare generated versus source-isolated performance.
- Conduct error decomposition for document quality, language, process variation, and legal scope.
- Do not tune on the source-isolated test panel.

## 21.8 Are generated artifacts realistic enough for the intended reasoning task?

### Decisive experiment

Blind reviewers rate:

- message plausibility;
- document plausibility;
- image plausibility;
- cross-document consistency;
- process plausibility;
- and whether generation source is detectable.

Record rejection reasons and agreement. A low source-identification rate alone is not enough; the cases must preserve task-relevant realism.

## 21.9 Does CasePath reduce expert or customer work?

### Decisive experiment

Under matched cases and expert time, compare:

- ordinary handling;
- static checklist;
- direct model assistant;
- CasePath process-grounded assistant.

Measure:

- customer-contact rounds;
- unnecessary requests;
- critical misses;
- time to decision-ready;
- expert interventions;
- expert confidence;
- and wrong-ready decisions.

## 21.10 Is the live multi-agent architecture better than a simpler pipeline?

### Decisive experiment

Hold canonical contracts and model budget constant.

Compare:

- one structured model call;
- sequential specialist calls;
- parallel specialist calls with orchestrator;
- deterministic pipeline;
- and hybrid model-plus-validator pipeline.

Measure accuracy, latency, cost, repair rate, trace usefulness, and failure recovery. Do not assume multi-agent decomposition is beneficial.

---

# 22. Immediate next milestone

## 22.1 Milestone

> **Produce one truthfully model-backed and independently reviewed recurring-mould flagship lifecycle without weakening the current v20 product experience.**

The existing v20 demo already shows the desired lifecycle. The next useful step is not another redesign. It is to replace the most consequential generated-reference assumptions with verified evidence.

## 22.2 Exact completion criteria

### Source package

- one recurring-mould claim with realistic message, lease, correspondence, photographs, chronology, and receipt;
- no visible or metadata generation leakage in the evaluated package;
- stable source hashes and page references;
- blind realism review by at least two independent reviewers;
- documented contradictions and intended unknowns.

### Canonicalization

- a replaceable model or hybrid canonicalizer reads only the observable package;
- every consequential fact has source provenance;
- unsupported-fact and conflict-handling gates pass;
- output conforms to the canonical schema;
- deterministic reference state remains available as an oracle, not hidden input.

### Process and evidence

- complete graph generated or instantiated from the canonical state;
- every evidence item links to node, fact, reason, and current source state;
- no repeat requests;
- alternatives and conditional items represented;
- graph and checklist pass deterministic validators.

### Law and precedent

- official-source passages versioned and linked to decisions;
- operational interpretations reviewed by a qualified Swiss tenant-law expert;
- prior cases retrieved without self- or source-family leakage;
- relevance reasons shown.

### Expert review

- at least two qualified reviewers independently review the graph and evidence model;
- corrections are typed and source-grounded;
- disagreements are adjudicated or represented as alternatives;
- review time and edit distance recorded.

### Learning and reuse

- reviewed case memory saved to durable storage;
- one candidate patch remains quarantined unless genuine support threshold is met;
- a second unseen claim retrieves the reviewed memory;
- any process or evidence effect is derived from the actual pipeline, not hard-coded;
- before/after is auditable.

### Engineering and product

- backend tests target the deployed pipeline;
- focused Playwright gate is fixed in master;
- local uninterrupted run passes;
- frontend, API, QA, and benchmark release manifest record exact SHAs;
- one production deployment after candidate freeze;
- no console, page, or request failures;
- 320 px and 390 px remain overflow-free;
- one first-time viewer can explain the lifecycle without narration.

## 22.3 What not to work on before this milestone

Do not:

- add claim categories;
- rebuild a broad claims inbox;
- add more agent types;
- add dashboards or metrics;
- create another process visualization;
- introduce `live-v21-*`;
- refactor the entire repository;
- design a general process-mining platform;
- run large live-model sweeps;
- write release announcements;
- or claim real-world benefit.

---

# 23. First 60 minutes

## First 10 minutes: understand the truth boundary

Read:

1. this file;
2. `casepath/index.html`;
3. `casepath/assets/live-v20-focus.js`;
4. `casepath-api/casepath_api/app.py`;
5. `casepath-api/casepath_api/pipeline_v15.py`;
6. `casepath-api/casepath_api/data.py`;
7. `casepath-api/casepath_api/storage.py`;
8. `casepath-qa/browser-focused-v20.mjs`.

Be able to state:

- public product has two generated claims;
- public pipeline is deterministic;
- public graph is 11-stage and handcrafted;
- evidence is node/fact linked;
- memory is SQLite and ephemeral;
- the hardened research benchmark is separate;
- live Nemotron is not current.

## Next 15 minutes: run the API and frontend locally

From a clean clone:

```bash
git clone https://github.com/KumarNavish/KumarNavish.github.io.git
cd KumarNavish.github.io

python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r casepath-api/requirements.txt

python casepath-api/generate_artifacts.py
PYTHONPATH=casepath-api \
CASEPATH_DB_PATH=/tmp/casepath-local.db \
uvicorn casepath_api.app:app --host 127.0.0.1 --port 8000
```

In a second terminal:

```bash
python3 -m http.server 4173 --directory casepath
```

Open:

```text
http://127.0.0.1:4173/?api=http%3A%2F%2F127.0.0.1%3A8000
```

Notes:

- `render-build.sh` downloads or verifies licensed photo replacements; use it when reproducing the Render build.
- Generated local photos may differ if the replacement step is skipped.
- Do not use production API for local destructive tests.

## Next 15 minutes: inspect product states

Verify manually:

1. claim message and six attachments;
2. lease PDF pages;
3. image;
4. “Analyse claim”;
5. source-level events;
6. graph takes over;
7. causation is current;
8. evidence status on nodes;
9. three precedents;
10. document needs derived from graph;
11. review delta;
12. learning summary;
13. later-claim before/after.

Open the audit trail and distinguish deterministic reference event metadata from model inference.

## Next 20 minutes: reproduce and repair the gate

Install QA dependencies:

```bash
cd casepath-qa
npm install --no-audit --no-fund
npx playwright install chromium
```

Before running the current master gate, repair these known assumptions:

```text
still-needed → needed
do not hard-code causation for the first document item
assert immutable v20 release meta/asset rather than mutable legacy global
```

Run against local services first. Then run against production only after local success.

Compare:

- screenshots;
- DOM assertions;
- run IDs;
- API result objects;
- console, page, and request errors;
- reset behavior.

Do not modify product code until you can explain:

```text
observable package
→ reference events
→ claim state
→ legal context
→ process graph
→ evidence model
→ precedents
→ expert correction
→ memory and candidate
→ later claim
```

---

# 24. Glossary

## Observable Claim Package

The customer message, submitted artifacts, and allowed intake metadata genuinely available to the downstream system. It excludes reference labels and generation provenance.

## Canonical Claim State

A typed, source-linked representation of facts, values, states, confidence, conflicts, and provenance derived from the observable package. It does not contain the final process or checklist answer.

## Process Graph

A versioned directed representation of handling decisions, steps, branches, conditions, owners, and terminal states.

## Process Instance

The complete graph plus the current claim overlay: completed, current, blocked, conditional, inactive, and available decisions.

## Evidence Requirement

A statement of what evidence could establish a fact required by a process decision. It is not synonymous with a filename.

## Document Checklist

A user-facing operational projection of applicable evidence requirements, grouped by current state. It must remain traceable to process decisions and facts.

## Reviewed Case Memory

A versioned record of one expert-reviewed claim, including source package, canonical state, process path, evidence state, corrections, reviewer status, and provenance. It may immediately support retrieval.

## Playbook

A versioned organizational representation of allowed handling structure and decision logic for a defined scope, including evidence relationships, sources, alternatives, and rollback.

## Candidate Knowledge Patch

A quarantined proposal to modify a playbook based on reviewed evidence. It is not shared knowledge until promotion gates pass.

## Protected Regression Set

A frozen collection of ordinary, edge, negative, and safety-critical cases used to ensure that a proposed change does not damage existing valid behavior.

## Agent

A bounded component that proposes one typed artifact or operation. An agent may be model-driven, deterministic, or hybrid; the implementation must be declared.

## Orchestrator

The component that coordinates stage order, shared context, retries, pauses, and artifact handoffs. It does not exempt stage outputs from validation.

## Expert Review

A qualified human’s structured validation or correction of facts, process, evidence, sources, or alternatives. Simulated review must not be called expert validation.

## Knowledge Consolidation

The controlled transformation of a reviewed case into immediate case memory and, where supported, a quarantined candidate reusable rule.

---

# 25. Operating rules for future collaborators

## 25.1 Preserve judgment, not just code

Before implementing, write down:

- which project layer you are changing;
- what evidence currently supports it;
- what failure it addresses;
- what invariant must not change;
- and what would falsify the improvement.

## 25.2 Do not claim more than the artifact supports

Use these phrases precisely:

- “generated reference,” not “ground truth,” unless expert-adjudicated;
- “deterministic reference agent,” not “LLM agent”;
- “official source linked,” not “legally validated”;
- “simulated review,” not “expert review”;
- “browser-verified,” not “user-validated”;
- “generated interaction simulation,” not “customer savings”;
- “candidate patch,” not “learned organizational rule.”

## 25.3 One source of truth per object

For each release, identify one authoritative file for:

- product version;
- API version;
- schema version;
- benchmark version;
- playbook version;
- deployment SHA;
- model ID;
- and evaluation manifest.

Current project state violates this rule. Fix it before the next release.

## 25.4 Do not rebuild solved infrastructure

Reuse:

- source viewer;
- page rendering;
- process graph renderer;
- node/fact/evidence contracts;
- event stream;
- review-to-memory lifecycle;
- browser recording;
- responsive layout;
- build-time artifact generation;
- and deterministic validation patterns.

Do not spend research time replacing them unless they block the milestone.

## 25.5 Do not hide failures behind polish

A polished two-pane UI cannot compensate for:

- predefined facts;
- static law mapping;
- hard-coded process graphs;
- unverified model calls;
- ephemeral memory;
- or missing expert validity.

Keep uncomfortable facts in the interface audit and in research reports.

## 25.6 Separate mechanism and end-to-end tracks

Mechanism track:

```text
adjudicated canonical state
→ process/evidence/retrieval/learning
```

End-to-end track:

```text
raw message and files
→ canonical state
→ process/evidence/retrieval/learning
```

Report both. If the mechanism works and end-to-end fails, the canonicalizer is the bottleneck. Do not obscure that with one aggregate score.

## 25.7 Freeze before confirmatory evaluation

Before accessing a confirmatory set, freeze:

- schema;
- process registry;
- document registry;
- prompt;
- model;
- provider;
- method;
- hyperparameters;
- split;
- metrics;
- thresholds;
- and analysis plan.

## 25.8 Treat deployment as verification, not design

- Design locally.
- Capture visual states.
- Run full local demo.
- Freeze candidate.
- Deploy once.
- Fix only deployment defects.
- Record exact SHAs.
- Preserve the failed and passing QA artifacts.

## 25.9 Avoid another architecture reset

The project has already explored:

- static playbooks;
- deterministic compilers;
- retrieval;
- rule induction;
- verified synthesis;
- durable state graphs;
- LangChain specialist agents;
- and front-end orchestration narratives.

The next milestone needs empirical truth and expert validation, not another orchestration framework.

## 25.10 Final self-test before modifying code

A new collaborator must be able to answer:

1. What is the real problem?
2. Which current component is deterministic?
3. Which current component is model-driven?
4. Which data are observable?
5. Which labels are hidden?
6. Which benchmark is being used?
7. What makes an evidence item applicable?
8. Why is causation unresolved in the flagship?
9. What did the expert correction change?
10. What is saved immediately?
11. What remains quarantined?
12. What exact result is generated-reference only?
13. Which current tests are misaligned?
14. What is the next milestone?
15. Which tempting work is explicitly out of scope?

If any answer is unclear, do not begin a broad code change.



# Appendix A: evidence and artifact registry

## A.1 Current product sources

| Artifact | Location | What it establishes |
|---|---|---|
| Frontend entry | [`casepath/index.html`](https://github.com/KumarNavish/KumarNavish.github.io/blob/master/casepath/index.html) | v20 release meta, intentional loading shell, two-pane structure, loaded layered assets |
| Focus behavior | [`live-v20-focus.js`](https://github.com/KumarNavish/KumarNavish.github.io/blob/master/casepath/assets/live-v20-focus.js) | graph-first moment detection, derived document sheet, focused review, learning, and later result |
| Focus style | [`live-v20-focus.css`](https://github.com/KumarNavish/KumarNavish.github.io/blob/master/casepath/assets/live-v20-focus.css) | one-third/two-thirds layout and removal of report framing |
| API | [`app.py`](https://github.com/KumarNavish/KumarNavish.github.io/blob/master/casepath-api/casepath_api/app.py) | public routes and import of `pipeline_v15` |
| Deployed pipeline | [`pipeline_v15.py`](https://github.com/KumarNavish/KumarNavish.github.io/blob/master/casepath-api/casepath_api/pipeline_v15.py) | deterministic full lifecycle |
| Public data | [`data.py`](https://github.com/KumarNavish/KumarNavish.github.io/blob/master/casepath-api/casepath_api/data.py) | two claims, nine artifacts, static law and historical cases |
| Storage | [`storage.py`](https://github.com/KumarNavish/KumarNavish.github.io/blob/master/casepath-api/casepath_api/storage.py) | SQLite tables and ephemeral default |
| Artifact generation | [`generate_artifacts.py`](https://github.com/KumarNavish/KumarNavish.github.io/blob/master/casepath-api/generate_artifacts.py) | generated PDFs, emails, and image construction |
| Build | [`render-build.sh`](https://github.com/KumarNavish/KumarNavish.github.io/blob/master/casepath-api/render-build.sh) | photo replacement, hashes, and smoke test |
| Focused gate | [`browser-focused-v20.mjs`](https://github.com/KumarNavish/KumarNavish.github.io/blob/master/casepath-qa/browser-focused-v20.mjs) | desired uninterrupted product assertions |
| Live product | <https://casepath-swiss-claim-lab.onrender.com/> | deployed v20 experience |
| Live API | <https://casepath-agentic-api.onrender.com/> | deployed reference API |
| Canonical QA | <https://casepath-guided-canonical-qa.onrender.com/> | retained browser evidence |
| Product commit | [`a867bb5`](https://github.com/KumarNavish/KumarNavish.github.io/commit/a867bb506d8e3f790806fc21f2a24a011c1cd0bc) | frozen focused product baseline |

## A.2 Original-corpus sources

The following were inspected as archived research artifacts rather than current default-branch files:

- `corpus-audit-v2.json`
- benchmark application pack and research brief
- `experiment-results.json`
- generated-plan reports
- source tree manifest
- benchmark package release reports

Key identifiers:

```text
contract: casepath.private-candidate-corpus/2.0.0
claims: 150
files: 2,251
corpus SHA-256:
84d827d30c8688c3e0ccfc71d89a3d64e96048eb2d2e43c32dd719a54209e966
reported source commit:
7bebdf3f9fc35641ee91262f61180b27362e99cc
```

The source commit was not found in the inspected GitHub repository. Recover its actual origin before relying on commit-based reproducibility.

## A.3 Hardened vertical-slice sources

Archived research artifacts:

- `manifest.json`
- `benchmark.py`
- deep-recovery report
- `experiment-report.md`
- adaptation comparison report
- error-propagation report
- interaction-simulation report
- simulated-pilot analysis
- `run_all.py`
- `bootstrap_and_verify.sh`
- browser smoke report
- release manifest and checksums
- expert-review package and preregistered plan

Key identifier:

```text
contract:
casepath.defects-vertical-slice-benchmark/1.0.0
```

## A.4 Historical model-driven sources

Archived sources:

- `langchain_agents.py`
- historical `app.py` reporting LangChain/LangGraph runtime
- call-budget plan
- model profiles
- old premium-minimal embedded release
- CasePath v3/v8 execution prompts

They establish that a model-driven architecture was implemented in another project generation. They do not establish that it is present in current master or live.

## A.5 Paper and research-formulation artifacts

Several paper generations exist:

- claim-readiness planning;
- process-grounded claim readiness;
- executable playbook induction;
- certified contrasts and literal-support audit;
- governed replacement;
- ICLR collaboration drafts.

They should be read as research-design history. Some explicitly state that workflow topology is supplied rather than discovered. Do not use them as proof that the current public product implements their full method or experiments.

---

# Appendix B: known defects and contradictions

## B.1 Critical truth and release defects

### B1. Current release markers disagree

```text
HTML: 20.0.0
API: 15.0.0
release.json: 12.0.2
source-manifest.json: 10.0.0
```

**Impact:** a new agent cannot determine release truth from repository metadata.

**Fix:** create a single generated release manifest containing product, API, QA, benchmark, schema, model, and deployment SHAs. Make old files clearly historical or regenerate them.

### B2. Current default-branch QA does not reproduce the retained pass without patches

**Impact:** a clean clone may fail even though the hosted canonical QA is green.

**Root causes observed:**

- stale `still-needed` selector;
- hard-coded causation return;
- mutable legacy global used as release marker.

**Fix:** merge corrected production gate into product master, run locally and on canonical QA, and store report hash.

### B3. Backend unit tests target the wrong pipeline

`casepath-api/tests/test_pipeline.py` imports `pipeline.py`; `app.py` imports `pipeline_v15.py`.

**Impact:** a passing unit test would not prove deployed pipeline behavior.

**Fix:** rewrite or parameterize tests against `pipeline_v15`. Keep legacy tests in a clearly named legacy folder if needed.

### B4. API build does not run the aligned test suite

`render-build.sh` runs a direct smoke, not pytest against v15.

**Impact:** regressions may deploy if the browser gate is not manually triggered.

**Fix:** run fast v15 unit tests in API build or CI; keep long browser gate separate.

### B5. Persistence is ephemeral

SQLite defaults to `/tmp`.

**Impact:** runs, reviews, memory, candidates, and playbook state may disappear on restart; no real pilot durability.

**Fix:** PostgreSQL, migrations, backups, transactional update and rollback.

## B.2 Research-validity defects

### B6. Public facts and outputs are predefined

**Impact:** the product demonstrates interaction but not model reasoning.

**Fix:** bounded model-backed canonicalizer with source validation; preserve deterministic oracle.

### B7. Public process graph is handcrafted

**Impact:** no evidence of claim-specific process inference.

**Fix:** evaluate instantiation from adjudicated and model canonical states.

### B8. Legal RAG is static and unapproved

**Impact:** cannot claim current legal retrieval quality or legal correctness.

**Fix:** versioned official-source corpus, retrieval evaluation, qualified review.

### B9. Public knowledge promotion is hard-coded generated reference

**Impact:** v3→v4 is a lifecycle story, not proof of safe learning.

**Fix:** run actual target/protected manifests and keep candidate quarantined until gates pass.

### B10. No qualified expert validation

**Impact:** process, evidence, law, and review usability remain unvalidated.

**Fix:** independent review, adjudication, and release of disagreement-aware targets.

### B11. No real-world transfer evaluation

**Impact:** generated performance cannot support operational claims.

**Fix:** approved source-isolated panel and frozen transfer study.

### B12. Artifact generation leaks “generated” markers

**Impact:** current files cannot serve as leakage-clean benchmark inputs.

**Fix:** separate public-demo disclosure shell from evaluated artifact bytes; remove answer-bearing metadata.

## B.3 Engineering and product defects

### B13. Layered frontend architecture is fragile

v16–v20 scripts and CSS all remain active.

**Impact:** DOM observation, mutable markers, duplicate behavior, and selector drift.

**Fix:** after milestone, consolidate into one tested runtime without changing interaction semantics.

### B14. No broad claim browsing in current v20

**Impact:** public product cannot demonstrate the 150-claim corpus.

**Decision:** this is intentional for flagship convergence. Do not treat it as immediate blocker.

### B15. Crawler-visible fallback is stale or sparse

Text-only crawlers may see a JavaScript-required loading shell.

**Impact:** automated web inspection may misreport current state.

**Fix:** keep intentional server-rendered shell and use browser QA as acceptance. Optional progressive enhancement later.

### B16. Accessibility is minimally tested

**Impact:** keyboard, focus, screen-reader, contrast, and reduced-motion behavior not comprehensively validated.

**Fix:** run axe, keyboard journey, focus-order tests, and screen-reader review after flagship truth milestone.

### B17. No user comprehension evidence

**Impact:** 57 browser checks validate mechanics, not understanding.

**Fix:** silent demo review with first-time viewers and structured comprehension questions.

## B.4 Data and provenance contradictions

### B18. Original benchmark source commit unavailable

**Impact:** Git-level reproducibility claim is incomplete.

**Fix:** recover archive repository, verify manifest against commit, document supersession.

### B19. Metric snapshots differ

Subject-only and longitudinal results differ across reports.

**Impact:** publication could accidentally mix versions.

**Fix:** attach every metric to benchmark hash, split manifest, code commit, and report timestamp.

### B20. Multiple Nemotron IDs

**Impact:** unclear model identity and cost.

**Fix:** one versioned model profile; log exact provider and model response.

### B21. Papers describe supplied workflows while product narrative says process discovery

**Impact:** scientific contribution can become internally contradictory.

**Fix:** explicitly choose whether the experiment studies workflow induction, graph instantiation, or graph discovery.

---

# Appendix C: release and research evolution

This timeline is conceptual. Use commit history for exact dates.

## C.1 Early product concept

The project began around a living library of tenant-law workflows and document checklists learned from expert traces.

The initial operational story was:

```text
incomplete claim
→ category-specific playbook
→ tailored checklist
→ expert correction
→ governed update
```

Useful insight: expert behavior is procedural weak supervision.

Limitation: category-level playbooks were too coarse and risked static checklisting.

## C.2 Original 150-claim benchmark

The project generated a large bilingual package with strong reproducibility and provenance.

Successes:

- 150 claims;
- 2,251 files;
- canonical artifacts;
- deterministic rebuild;
- large internal test suite.

Failures discovered:

- subject shortcut;
- one process skeleton per category;
- no longitudinal state;
- no negative cases;
- weak attachment density;
- generated labels.

Decision: retain as infrastructure proof and historical baseline, not decisive benchmark.

## C.3 Defects vertical slice

The project narrowed to defects and built longitudinal journeys, attachment-rich cases, negatives, and a withheld ventilation pattern.

Successes:

- harder intake task;
- claim-specific process variation;
- staged evidence;
- negative scope;
- three-valued process logic;
- sparse adaptation experiments.

Decision: one strong vertical slice before broad category expansion.

## C.4 Expert-ready research release

The project added:

- 30-case review package;
- typed corrections;
- disagreement-aware targets;
- adaptation comparison;
- error propagation;
- interaction simulation;
- simulated reviewer dry run;
- reproducibility tooling.

Success: scientific failure modes became explicit and executable.

Boundary: still generated, simulated, and not independently expert-approved.

## C.5 DurableClaimGraph and model-provider generation

A later architecture emphasized:

- explicit state;
- deterministic compilers;
- provider-independent model adapters;
- OpenRouter Nemotron;
- audit and persistence;
- governed updates.

Release work encountered source-transfer, deployment, persistence, live-call, and clean-room blockers.

Decision: preserve contracts and safety scaffold; do not claim live model success.

## C.6 LangChain agentic OS generation

Another generation used LangChain `create_agent` on LangGraph runtime with specialist agents and shared context.

Success: architecture matched the “team of agents” narrative.

Boundary: live calls and current deployment were not consistently verified; source did not remain in current master.

Decision: treat as historical implementation reference, not current truth.

## C.7 Product-convergence releases v13–v20

The project repeatedly redesigned the public demo:

- live agent events;
- persistent source claim;
- process graph in main canvas;
- evidence on graph;
- contextual law;
- contextual precedents;
- expert review;
- memory and later claim;
- reduced report framing.

v20’s main contribution is not new backend intelligence. It is product hierarchy:

```text
one source claim
+ one dominant artifact
+ one next action
```

Decision: freeze UX and pursue truth/validation.

---

# Appendix D: capability claim matrix

Use this table when writing papers, applications, demos, or presentations.

| Potential statement | Allowed wording now | Forbidden wording now |
|---|---|---|
| Product status | “A live browser-verified research demonstration” | “Production claim-handling system” |
| Agent execution | “Typed reference-agent stages emit real backend events” | “Nemotron agents handled the claim” |
| Documents | “Generated source artifacts are inspectable” | “Real customer documents” |
| Process | “The demo constructs and displays a complete reference process graph” | “The system learned the true handling process” |
| Evidence | “Reference evidence items are linked to process decisions and facts” | “The system proved which documents are legally required” |
| Law | “Official-source references are linked to process nodes” | “The workflow is legally validated” |
| Precedents | “Generated references and reviewed demo memory are retrieved” | “Historical production claims improve decisions” |
| Review | “A structured demo correction changes downstream artifacts” | “Experts validated the method” |
| Learning | “The demo illustrates memory and a generated v4 promotion” | “The organization safely learned a new rule” |
| Benefit | “Generated simulation reduced unnecessary requests” | “CasePath reduces customer follow-up” |
| Benchmark | “Generated bilingual corpus and hardened defects benchmark” | “Real-world benchmark” |
| Reproducibility | “Specific archived releases reported clean internal verification” | “The current integrated system is independently reproduced” |
| Live model | “Historical OpenRouter/Nemotron integration exists” | “The current deployment runs Nemotron” |

---

# Appendix E: adversarial handoff quality check

This file was reviewed against the following questions.

## E.1 Can a new agent understand the real problem?

Yes: the mission, operational rationale, and process→fact→evidence dependency are stated before implementation detail.

## E.2 Can a new agent distinguish current implementation from aspiration?

Yes: current public deterministic reference, archived LangChain architecture, original corpus, hardened benchmark, and planned experiments are separated.

## E.3 Can a new agent identify what is working?

Yes: the v20 browser-verified journey, source rendering, event stream, graph, evidence linkage, review interaction, memory, and later-claim demo are listed with status.

## E.4 Can a new agent identify what is simulated or generated?

Yes: every research result and public lifecycle component is marked generated-reference where appropriate.

## E.5 Can a new agent understand the benchmark?

Yes: original corpus and hardened vertical slice have separate counts, contracts, defects, and availability.

## E.6 Can a new agent understand the agent pipeline?

Yes: current deterministic specialists and historical model-driven specialists have explicit contracts and status.

## E.7 Can a new agent understand process, evidence, and law?

Yes: canonical dependency chain and separate legal objects are explicit.

## E.8 Can a new agent understand learning?

Yes: reviewed memory and candidate shared knowledge are separated, with promotion gates and public-demo limitations.

## E.9 Can a new agent avoid repeated failures?

Yes: the “Do not rediscover” table records failed methods, UX patterns, and deployment workflow.

## E.10 Can a new agent locate code?

Yes: current frontend, backend, QA, build, storage, and archived research paths are mapped.

## E.11 Can a new agent run the system?

Yes: local API/frontend commands and known QA repairs are documented.

## E.12 Can a new agent identify the biggest blocker?

Yes: the current blocker is evidence validity—realistic leakage-clean flagship input, model-backed canonicalization, qualified expert review, genuine regression-backed learning, and durable storage—not missing UI functionality.

## E.13 Does a new agent know exactly what to do next?

Yes: Section 22 defines one milestone with completion criteria and explicit exclusions.

## E.14 Hidden assumptions deliberately surfaced

- “Agents” may be deterministic.
- “RAG” may be a static registry.
- “Reviewed” may be simulated.
- “Learning” may be hard-coded reference output.
- “Current release” differs by component.
- “Benchmark” refers to multiple incompatible assets.
- “Reproducible” may refer to an archived package, not current integrated master.
- “Process discovery” may mean graph instantiation rather than topology discovery.
- “Realistic” lacks blind human validation.
- “Durable” is false for current `/tmp` SQLite.

---

## Final handoff directive

Do not begin by adding code.

First reproduce the current flagship journey, recover the hardened benchmark release, and write a one-page discrepancy list between:

```text
what the current product shows
what the current API computes
what the benchmark evaluates
what the paper claims
what experts have actually validated
```

Only then begin the immediate milestone in Section 22.

The best next contribution is not more machinery. It is to make one lifecycle simultaneously:

- visually clear;
- technically aligned;
- source-grounded;
- model-truthful;
- expert-reviewed;
- regression-tested;
- durable;
- and honestly described.

---

<!-- BEGIN CASEPATH IMPLEMENTATION CONVERGENCE RECORD: 2026-08-11 -->

# 2026-08-11 implementation-convergence record

> **Status:** source-converged candidate; deterministic checks partially complete;
> accepted model-backed, independent-review, and deployment-alignment evidence
> pending.
>
> **Authority:** the 4,029 lines above are the authoritative reconstructed
> knowledge transfer supplied on 11 August 2026. This delimited record is a
> point-in-time correction for the convergence worktree. Where a current-state
> statement above conflicts with this record, use this record for the convergence
> candidate and preserve the older statement as historical evidence.

## Record scope and source identity

| Field | Value |
|---|---|
| Canonical repository | `KumarNavish/KumarNavish.github.io` |
| Local checkout | `/Users/kumar0002/Documents/Die Mobiliar/casepath-canonical` |
| Canonical remote branch fetched | `origin/master` |
| Fetched baseline at audit start | `48c216c4c3c9ce93ff970ad3a20b3fc86f3e0f99` |
| Convergence worktree branch | `codex/casepath-convergence` |
| Candidate source commit | **PENDING — convergence work is not yet frozen or committed** |
| Current deployed source identity | **PENDING — not established by this worktree audit** |
| Alignment status | **NOT PROVEN** |

The source architecture, tests, and documents described below are uncommitted
candidate state unless a later finalization record binds them to a commit. They
must not be described as deployed merely because they exist in the checkout.

## Converged source architecture

The convergence candidate preserves the two generated public claims and the
graph-first v20 journey while tightening authority boundaries:

```text
generated observable claim package
→ deterministic reference canonicalizer by default
  OR one bounded OpenRouter canonicalization call when explicitly enabled
→ deterministic fact-to-decision projection
→ static, unapproved legal-reference mapping
→ deterministic process and evidence construction
→ executable contract and grounding validators
→ generated-reference precedent retrieval
→ narrow generated-demo review
→ unverified reviewed-case memory
→ quarantined candidate; shared playbook v3 unchanged
→ explicit baseline/current later-claim runs
→ computed run-bound comparison, not a quality claim
```

The replaceable boundary is the source-linked canonical claim state. Model output
cannot own graph integrity, process-control metadata, review authority,
promotion, source provenance, budget enforcement, or release identity.
`casepath-api/casepath_api/canonicalizer.py` contains the optional bounded
adapter. `casepath-api/casepath_api/validation.py` and deterministic pipeline
code remain authoritative for accepted artifacts.

### Canonicalization modes

| Mode | Current source behavior | Truth boundary |
|---|---|---|
| `deterministic_reference` | Default; uses the generated reference fact catalog and performs no network call | Implemented and deterministically tested; still generated-reference only |
| `openrouter_nemotron` | Optional; one structured canonicalization request for the observable package, then deterministic merge and validation | Adapter implemented; authorized attempt 1 failed closed and is not accepted model-backed evidence |
| Downstream process/evidence | Deterministic projection, graph construction, evidence construction, retrieval, and validators | Implemented for the two generated claims; not general model inference |

The configured requested model identity is
`nvidia/nemotron-3-ultra-550b-a55b`. One provider attempt returned usage but the
application rejected its source-reference contract, so the release has no
accepted model-backed execution evidence.

## Backend behavior

The candidate API/pipeline reports component version 15.2.0 while the frontend
retains product version 20.0.0. These are independent component versions under
one release contract.

Implemented source behavior:

- state-changing and session-state endpoints require an opaque
  `X-CasePath-Session` identifier;
- runs, reviews, memories, candidates, reads, and reset are scoped to the caller's
  demo session;
- reset preserves other sessions and the global sanitized model-call ledger;
- the default database is still resettable SQLite and is not durable pilot
  infrastructure;
- review requests use bounded enums;
- rejection creates neither reviewed memory nor a candidate;
- an accepted generated-demo edit is labelled
  `unverified_demo_review`/`unverified_demo_memory`;
- one accepted edit creates support `1/3`, target tests `not_run`, protected
  regression `not_run`, approval `pending`, and a quarantined candidate;
- shared knowledge remains `mould-playbook-v3`;
- later-claim proof requires two explicitly bound, distinct, completed runs:
  baseline knowledge mode and current knowledge mode;
- the proof reports observed result differences and reviewed-memory retrieval;
  it does not claim improvement or shared-rule promotion;
- validators execute against claim state, exact source grounding, law provenance,
  process topology, evidence links, current-state projection, precedents, and
  post-review artifacts;
- the public model ledger exposes only a fixed sanitized field set and not prompt
  or canonical-output payloads.

The OpenRouter path fails closed on missing credentials, wrong response model,
missing positive paid-usage evidence, invalid structured output, hallucinated or
wrong-page quotations, malformed/duplicate/unregistered source-reference IDs,
and cumulative cost guard violations. A registered but nonexact source set,
including an incomplete conflict-side selection, cannot control final citations:
it is replaced by the application-owned exact source set and disclosed as a
source-reference projection. Its default cumulative cap is USD 25 and can only be
configured downward. These are implementation and mocked-test facts, not proof
of an accepted model-backed run. The retained first attempt failed closed on an
exact-private-reference mismatch and bound no successful ledger call.

## Frontend behavior

The source candidate keeps the focused v20 visual journey and removes
success-biased learning claims:

- one immutable static v20 release marker replaces competing timed release
  writes;
- the core renderer emits explicit `casepath:render` transitions;
- the 11-node main spine remains the default reading path;
- every non-spine node, branch, and graph edge is inspectable through progressive
  disclosure in the main workspace;
- decision facts render every typed source reference, locator, agent, state, and
  confidence, with source-to-fact and fact-to-source navigation;
- document needs derive their owning decision structurally;
- the review view renders the actual graph/evidence delta;
- missing candidate proof is not replaced by passing defaults;
- the learning view says the reviewed memory is unverified, the candidate is
  quarantined at one of three, evaluations have not run, and shared v3 is
  unchanged;
- the PDF viewer includes extracted-text search, WAI-ARIA tab behavior,
  busy-state clearing, modal focus management, and focus restoration;
- compact mobile provenance and graph controls remain present in source.

This record does not claim that those interactions have passed the current
Playwright journey or a deployed browser run.

## QA behavior

`casepath-qa/browser-focused-v20.mjs` is now the canonical focused gate in
source. It includes:

- an explicit opt-in before mutating non-local services;
- frontend/API/QA release-ID and non-unknown source-commit equality checks for
  production;
- caller-session isolation and cross-session denial checks;
- complete process-node and edge coverage;
- exact text-quote, metadata, and visual-observation grounding checks;
- derived document-owner navigation;
- rejection/quarantine/shared-v3 truth checks;
- baseline/current run-bound later-claim proof;
- sanitized model-ledger inspection;
- serious/critical axe checks, keyboard/focus checks, and responsive overflow
  checks;
- evidence retention plus reset/cleanup in `finally`.

For a non-local run, the gate requires one cold visible flagship orchestration
with all six successful paid OpenRouter/Nemotron ledger records bound to the
journey, including exact response models, distinct response and call IDs,
positive token counts, positive actual cost, strict accepted majorities, and
all three passed deterministic gates. This record does not contain a passing
production QA artifact pair; the fourteen retained attempts remain
failed-closed history and do not satisfy the production condition.

## Release and artifact behavior

`casepath/release.json` remains the static release criteria contract. Contract
2.2 deliberately embeds neither a source commit nor a mutable production
runtime verdict: recording a post-QA `passed` result in source would create a
new commit that the QA run did not test. Current runtime truth is decided only
from one atomic, same-commit `report.json` and `evidence-manifest.json` pair.
The tracked truth fields are therefore:

```text
generated_data_only: true
deterministic_build.status: passed
deterministic_build.execution_mode: deterministic_reference
deterministic_build.model_calls: 0
deterministic_build.model_backed: false
production_runtime_acceptance.verdict_authority: dynamic_same_commit_qa_artifacts
production_runtime_acceptance.source_contract_embeds_runtime_verdict: false
production_runtime_acceptance.required_mode: openrouter_nemotron
production_runtime_acceptance.required_provider_max_in_flight: 1
production_runtime_acceptance.dynamic_evidence.report_path: report.json
production_runtime_acceptance.dynamic_evidence.evidence_manifest_path: evidence-manifest.json
historical_model_validation.scope: failed_closed_history_only
historical_model_validation.establishes_current_runtime_acceptance: false
agentic_runtime.safety.provider_max_in_flight: 1
independent_expert_review: false
blind_review_completed: false
legal_approval: false
operational_validation: false
real_claims_approved: false
source_identity.authority: dynamic_same_commit_qa_artifacts
source_identity.source_contract_embeds_commit: false
```

The release tooling inventories source, browser gates, and model-visible
artifacts; builds a separate deployment identity; verifies scenario-date
ordering; checks deterministic artifact hashes; and scans PDF text/metadata,
email content/headers, image metadata, and raw bytes for construction markers.
The application shell retains the generated-data disclosure while evaluated
artifact bytes are isolated from that disclosure.

A mechanical leakage scan is not a blind realism result. The generated documents
remain research inputs until independent review is completed.

The external hardened benchmark ZIP is not copied into this repository. The
repository stores its SHA-256 sidecar and a release record that preserves:

- 2,581 internally hash-verified archive files;
- 1,721 passing tests in a recovered clean environment;
- an unresolved declared source commit;
- generated/simulated-only truth status;
- and the inherited non-idempotent 195-PNG preview rebuild failure.

That record improves provenance; it does not turn the archive into expert truth
or a current production benchmark.

## Generated-only and unverified boundary

| Surface | Allowed current statement | Still not established |
|---|---|---|
| Claims and source artifacts | Two generated research claims with deterministic, hash-bound artifacts | Real-claim validity or operational representativeness |
| Canonical claim state | Deterministic reference path is implemented; one bounded model adapter and one failed-closed attempt record exist | Accepted call-bound model-backed canonicalization |
| Law | Official-source references and unapproved operational mappings are linked | Qualified Swiss-law approval |
| Process and evidence | Typed graph/evidence contracts and validators run for two reference claims | General claim-specific inference or legal correctness |
| Precedents | Static generated references plus explicitly unverified demo memory | Reviewed production-history retrieval |
| Review | A constrained generated-demo edit is recorded and revalidated | Qualified expert review |
| Learning | Memory retrieval and a quarantined `1/3` candidate are demonstrated | Shared-rule promotion, fresh target tests, or protected regression |
| Persistence | Caller-session isolation exists in resettable SQLite demo storage | Durable, tenant-authorized pilot persistence |
| QA | Canonical gate source and deterministic syntax exist | Current uninterrupted Playwright pass or production evidence |
| Release | Contract and identity tooling exist | Frozen deployed commit or frontend/API/QA alignment |

## Deterministic validation recorded in this audit

Commands were run against the unfrozen convergence worktree on 11 August 2026:

| Command | Result |
|---|---|
| `PYTHONPATH=casepath-api python -m pytest -q casepath-api/tests` | **57 passed** |
| `python -m pytest -q casepath/tools/test_build_deployment_identity.py` | **2 passed** |
| `python -m pytest -q casepath/tools/test_casepath_release.py -k 'not test_release_contract_and_manifests_are_current'` | **10 passed, 1 deselected** |
| Combined backend/release-tool run before final source-manifest regeneration | **69 passed, 1 failed**; the only failure was exact source-manifest currency after concurrent source edits |
| `node --check casepath-qa/browser-focused-v20.mjs` | **passed** |
| `node --check casepath/assets/live-v16.js` | **passed** |
| `node --check casepath/assets/live-v20-focus.js` | **passed** |

The source-manifest mismatch is not waived. Finalization must regenerate the
manifest after all source changes, run the complete deterministic suite without
deselection, and record the resulting manifest hash.

Not run by this documentation audit:

- current uninterrupted local Playwright journey;
- current 320 px and 390 px visual acceptance;
- current production Playwright journey;
- independent blind realism review;
- qualified claim-process or Swiss-law review;
- accepted paid model retry after the retained failed-closed attempt;
- durable-storage migration/rollback;
- aligned Render deployment.

The 57/57 browser result described earlier in this transfer belongs to the
historical retained v20 evidence. It is not evidence for this convergence
worktree.

## Post-record production attempt 05 and canonical projection repair

The first same-commit production flagship was executed on source commit
`89519b7b00c4e3ff1bc0a2719ed9546b90e46c92`. Frontend and API identity were
aligned, readiness proved the exact Nemotron/LangGraph runtime and credential,
and QA opened one cold flagship run. The canonical-facts provider call returned
normally with valid structured content and complete usage, but the application
failed closed before any downstream specialist ran.

Sanitized evidence shows that Nemotron produced the complete 18-fact shape,
passed label/confidence/normalized-value checks, and matched 17 of 18 canonical
states. Seven zero-text-reference facts were accepted. Ten otherwise
semantically valid text-grounded facts were rejected only because their valid
observable passage IDs did not exactly equal one hidden, shortest private-oracle
segmentation; `fact_date_conflict` was rejected for `canonical_state`. The 7:11
count correctly failed the then-current strict-majority gate, but exposed a
contract-design defect rather than a provider, parsing, billing or deployment
failure.

The candidate source now separates semantic contribution from authoritative
source binding. Malformed, duplicate or unregistered reference IDs and any
state/polarity mismatch still reject a fact. A structurally valid observable
reference proposal whose ID set is not exactly the private resolved canonical
set—including a broader passage that fully contains the required quote—does not
control the final citations: the deterministic source gate projects the complete
exact source set and records
`source_reference_projection_fact_ids/count`. The model contributes only a
semantically verified state and confidence; canonical prose, process metadata
and exact citations remain application-owned. This is disclosed separately from
semantic deterministic fallback and is bound across run audit, visible receipt,
sanitized ledger, QA and runtime-evidence verification.

A production-shaped local regression using the exact 23,141/1,931-token attempt
shape now completes with 17 accepted semantic contributions, one canonical-state
fallback and ten deterministic source projections. The frozen candidate then
passed source/artifact manifest verification, 145 combined Python tests, the
40-fixture QA contract self-test, changed-file Ruff/compile/syntax/diff checks,
and the complete deterministic Render build. A fresh adversarial audit reported
no remaining P0/P1 blocker. The repair was published as source commit
`697a19fa0be541f46af85d9f31dd5cbda96b2bb8`, deployed with aligned frontend and
API identity, and exercised by the second same-commit paid request below.

## Production attempt 06 and upstream-provider persistence boundary

The second same-commit production gate ran from QA deploy
`dep-d9tnp72jobas73df6jmg` against aligned source commit
`697a19fa0be541f46af85d9f31dd5cbda96b2bb8`. Exactly one canonical-facts
provider response returned successfully from OpenRouter using the requested
Nemotron alias. Response `gen-1786477748-NYzcfF7sy7RQ71QO780m` charged USD
0.0177709 for 23,163 prompt and 2,825 completion tokens, 25,988 total, with
`stop`. The sanitized ledger recorded call `modelcall_0263759a564abb00` under
orchestration `orch_2d81acf782aa379b` and then failed closed with `KeyError`.

The synchronous response retained complete usage, response identity and finish
reason but not an upstream-provider value. The deployed metadata-backfill
predicate therefore skipped the generation lookup, while canonical-result
persistence later indexed the absent upstream-provider field. The source order
proves that canonical source merge, claim-state validation and exact-source
validation necessarily completed before that failing expression. It does not
prove any accepted/rejected or source-projection count: the exception occurred
before those diagnostics were finalized in the sanitized ledger, so this record
deliberately retains no such counts. No downstream model role or deterministic
gate produced a receipt, and the QA build failed closed. This remains historical
failure evidence, not current model-backed runtime acceptance.

The exact failed attempt is retained in
`casepath/releases/model-validation-attempt-20260811-06.json`. Known aggregate
charges for attempts 1, 2, 4, 5 and 6 are USD 0.0528110; attempt 3 remains
unknown and excluded rather than treated as zero.

## Production attempt 07 and SDK response-schema boundary

The next aligned gate ran from QA deploy `dep-d9to5onavr4c73c9lh3g` against
source commit `7e87f40bc866444f16fd837fa3e6a999faa1c7e0`. Frontend deploy
`dep-d9to4r942hec738ntcdg` and API deploy `dep-d9to4qqjnfac73cc5seg` were live
on that same commit. QA created run `run_a4ce02e0125690b2`; the first and only
model call was `modelcall_2c6614b3bc53305b` under orchestration
`orch_60c6c6a9508c39f9`.

OpenRouter returned an HTTP 200 JSON response after 28,814.669 ms, but
`openrouter` SDK 0.11.46 raised `ResponseValidationError` while decoding it as
`ChatResult`. That exception occurred before the LangChain adapter returned an
envelope, so CasePath retained no response ID/model, upstream provider, finish
reason, usage source, token counts, or actual cost. The ledger's USD 0.027645
value is only the pre-call estimated reservation; it is not evidence of a
charge. Actual cost and response identity remain unknown and unverified, and
the aggregate's zero-valued missing usage must not be read as a zero charge.

No canonical contribution was accepted, no downstream agent or deterministic
gate produced a receipt, and QA deploy `dep-d9to5onavr4c73c9lh3g` failed its
build. Its failed run was reset and is no longer retrievable; the public model
ledger is instance-ephemeral, and the failed QA deploy did not publish an
attempt-07 report or evidence manifest. The sanitized record is retained at
`casepath/releases/model-validation-attempt-20260811-07.json`. Known charges
remain USD 0.0528110 for attempts 1, 2, 4, 5 and 6; attempts 3 and 7 are
excluded as unknown rather than treated as zero.

The bounded source repair retains LangChain/LangGraph as the runtime and makes
no second inference attempt. A facade around the pinned OpenRouter client's
`chat.send` catches only `ResponseValidationError`, transiently validates a
size-bounded HTTP 200 JSON completion with one assistant string choice, removes
all response fields CasePath does not consume, and passes the projected dict
back into `ChatOpenRouter`'s native strict structured-output parser. Duplicate
keys, non-finite numbers, excessive nesting/size, error envelopes, or incomplete
identity fail under the constant `provider_response_envelope` invariant after
the raw SDK exception has left scope. The raw body is not logged or persisted.
Local pinned-SDK replay and canonical/specialist boundary tests pass; CP-020 is
`fixed_unverified` until a fresh same-commit production acceptance journey
proves the six roles and three deterministic gates.

## Production attempt 08 and eventual generation-metadata availability

The next gate ran from QA deploy `dep-d9tont6gekts7394fu50` against source
commit `2ab71f600f1e523388dec62e11da4c85b9a15be7`. The QA deploy ran from
2026-08-11T20:54:12.154773Z through 2026-08-11T20:54:58.013224Z. Its runtime
error was recorded at 2026-08-11T20:54:57.057789659Z, its build was marked
failed at 2026-08-11T20:54:57.157747982Z, and the final deploy outcome was
`build_failed`. QA run `run_06fb240a468fd0c8` made exactly one canonical-facts
call, `modelcall_58f841d20124e35f`, under orchestration
`orch_0083b550d06c4b83`; no downstream model call, agent receipt, or
deterministic-gate receipt followed.

The response bridge retained completion
`gen-1786481671-XHJr7oDjH1PtrUL2kNg3` using the exact requested response alias.
It recorded 23,163 prompt and 2,897 completion tokens, 26,060 total, USD
0.0179293, `stop`, and 25,938.06 ms latency. The application then rejected the
call with `ModelResponseError` under `generation_metadata_completeness`: the
same generation's upstream metadata was not available before the bounded
lookup ended, so no canonical result was accepted.

A later read-only lookup for that exact response returned the dated model
`nvidia/nemotron-3-ultra-550b-a55b-20260604`, upstream provider DeepInfra, and
the same cost, token counts, and finish reason. That observation proves eventual
metadata availability and that the deployed lookup ended too early. It does not
retroactively accept the run or create any missing downstream receipt. The
sanitized record is retained at
`casepath/releases/model-validation-attempt-20260811-08.json`; CP-021 remains
`in_progress` until delayed availability and a terminal timeout are both covered
without a second inference call and an aligned production journey passes.

## Production attempt 09 and upstream rejection

Attempt 09 ran from QA deploy `dep-d9tp3fjncjis739pbnrg` against source commit
`1464e482503f2b22bebffaa01a9cff84e70113ff`. The deploy was created at
2026-08-11T21:18:54.833304Z, finished `build_failed` at
2026-08-11T21:19:50.743049Z, and retained QA run
`run_3abf4f5dcf955488`. Its sanitized ledger retained one CasePath network
call: canonical-facts call `modelcall_eda1fe14d069e2d4` under orchestration
`orch_16fbcb9e76eaff90`. The ledger was created at
2026-08-11T21:19:16.695619+00:00 and finalized as `failed` at
2026-08-11T21:19:45.558899+00:00. It records 28,858.701 ms application latency,
`ModelResponseError`, and the constant `provider_response_envelope` invariant.
No downstream model call followed.

The signed-in OpenRouter Upstream Requests view showed the corresponding
request, `gen-1786483159-hyYthqPv76o6PHXpGLzl`, at 23:19 Europe/Zurich.
OpenRouter's default provider routing made two router-level upstream attempts;
Together was the final provider and returned status 400 after 759 ms of router
latency. The prior DeepInfra request returned 200. This is one CasePath
inference network call with two provider-routing attempts, not an application
retry. The exact internal provider error message remains unknown. A read-only
`GET /api/v1/generation` lookup for that exact request ID returned 404.
Consequently, no completed generation, response usage, token count, or actual
cost was recovered, and the request ID is not an accepted response identity.

The ledger's USD 0.027645 value is only an estimated reservation. The actual
charge remains unknown and is not included in the aggregate. No canonical
result was accepted and no model-backed release evidence was established. The
sanitized record is retained at
`casepath/releases/model-validation-attempt-20260811-09.json`. The current
source now pins the exact `together` endpoint tag, disables provider
fallbacks, requires parameter support, denies provider data collection, and
accepts successful provenance only from `Together`. It enables generation
metadata through the `X-OpenRouter-Metadata: enabled` request header, never the
prompt or JSON body. Those controls are locally verified but do not promote the
failed attempt; CP-022 remains production-unverified until a same-commit
journey passes.

## Production attempt 10 and orchestrator output ceiling

Attempt 10 ran from QA deploy `dep-d9tq5bmgekts73978kdg` against source commit
`0c73193688db85be2e84a8a83b73e311581e3874`. Render records a deploy start at
2026-08-11T22:31:10.393462Z, creation at 2026-08-11T22:31:10.431539Z, the
terminal QA error at 2026-08-11T22:33:15.916134259Z, and `build_failed`
completion at 2026-08-11T22:33:20.129521Z. The QA log binds run
`run_d2c28f11f5a4b30e` to orchestration `orch_4306b740e7a14b00`.

The public sanitized ledger contains exactly two network calls, both from
DeepInfra. Canonical-facts call `modelcall_1079d5361af8d6b8`, response
`gen-1786487495-uThNkWVHk7bkiuVb8vaP`, completed with `stop` and disclosed
guarded fallback. It retained 17 accepted and one rejected fact contribution,
23,163 prompt and 3,783 completion tokens, USD 0.0198785, and 85,972.266 ms
latency. Its ledger interval was 2026-08-11T22:31:31.379439+00:00 through
2026-08-11T22:32:57.367156+00:00.

Orchestrator-plan call `modelcall_0be219e96b14ec27`, response
`gen-1786487581-HBwGLlRWSJnrBZXAU3Y9`, then returned `length` at exactly 400
completion tokens. It retained 20,034 prompt tokens, 20,434 total, USD
0.0108714, 12,309.811 ms latency, `AgentBoundaryError`, and the constant
`provider_finish_reason` invariant. Its ledger interval was
2026-08-11T22:33:00.980714+00:00 through
2026-08-11T22:33:13.302269+00:00. The aggregate is cost-complete at USD
0.0307499 for 43,197 prompt and 4,183 completion tokens, with no unknown-cost
call.

CasePath correctly rejected the truncated plan. No later specialist call or
deterministic gate ran, the full orchestration was not accepted, and this
failed QA build establishes no current runtime acceptance. The sanitized record
is retained at
`casepath/releases/model-validation-attempt-20260811-10.json`. CP-023 raises
only the orchestrator plan ceiling from 400 to 800 tokens and retains the
fail-closed `length` boundary at the new ceiling; its local regression evidence
does not promote attempt 10 or replace a same-commit production journey.

## Production attempt 11 and unresolved orchestrator output ceiling

Attempt 11 ran from QA deploy `dep-d9tqd4ht0dsc73bthmgg` against source commit
`d59978be2f1824f6d769f6f2e32fb7a13e3843e7`. Render records a deploy start at
2026-08-11T22:47:46.222303Z, creation at 2026-08-11T22:47:46.251804Z, the
terminal QA error at 2026-08-11T22:48:48.17386701Z, the build-failed marker at
2026-08-11T22:48:48.211155358Z, and deploy completion at
2026-08-11T22:48:49.788544Z. The QA log binds run
`run_bdd1832d34d2188f` to orchestration `orch_6ca09d18eed0e3f6`.

The public sanitized ledger contains exactly two network calls, both from
DeepInfra. Canonical-facts call `modelcall_0e3ac23f5327d9de`, response
`gen-1786488490-tndMk9aYrOZRx6zRO0bs`, completed with `stop` and disclosed
guarded fallback. It retained 17 accepted and one rejected fact contribution,
23,163 prompt and 2,432 completion tokens, USD 0.0169063, and 25,695.53 ms
latency. Its ledger interval was 2026-08-11T22:48:07.570335+00:00 through
2026-08-11T22:48:33.279294+00:00.

Orchestrator-plan call `modelcall_72e43889f3f0bece`, response
`gen-1786488517-b5k43pHtTXGdyxrtSIP8`, then returned `length` at exactly 800
completion tokens. It retained 20,034 prompt tokens, 20,834 total, USD
0.0117514, 9,017.156 ms latency, `AgentBoundaryError`, and the constant
`provider_finish_reason` invariant. Its ledger interval was
2026-08-11T22:48:36.865710+00:00 through
2026-08-11T22:48:45.892252+00:00. The aggregate is cost-complete at USD
0.0286577 for 43,197 prompt and 3,232 completion tokens, with no unknown-cost
call.

CasePath correctly rejected the second truncated plan. No later specialist
call or deterministic gate ran, the full orchestration was not accepted, and
this failed QA build establishes no current runtime acceptance. The sanitized
record is retained at
`casepath/releases/model-validation-attempt-20260811-11.json`. Attempt 11
proves that the 800-token change did not resolve CP-023; that defect is again
in progress and requires a new source repair plus an aligned production
journey.

## Production attempt 12 and process-decision contribution boundary

Attempt 12 ran from QA deploy `dep-d9tqqlfavr4c73cfqb0g` against source commit
`a839ff99870f5be11f232d1bfc818854202bd2dd`. Render records a deploy start at
2026-08-11T23:16:37.149773Z, creation at 2026-08-11T23:16:37.178532Z, the
terminal QA error at 2026-08-11T23:18:55.342617058Z, the build-failed marker at
2026-08-11T23:18:55.38377292Z, and deploy completion at
2026-08-11T23:18:56.810953Z. The public QA log binds run
`run_403c755cd290a3dc` to orchestration `orch_bdc09ac146345588`.

The public sanitized ledger contains exactly four network calls, all from
DeepInfra. Canonical-facts call `modelcall_f738b46b703992a2`, response
`gen-1786490215-0nOpYjNjTeMxtSF7ZbzI`, completed with `stop` and disclosed
guarded fallback. It retained 17 accepted and one rejected fact contribution,
11 source-reference projections, 23,171 prompt and 2,736 completion tokens,
USD 0.0175791, and 44,011.294 ms latency. Its ledger interval was
2026-08-11T23:16:52.937497+00:00 through
2026-08-11T23:17:36.966427+00:00.

The bounded orchestrator-plan call `modelcall_19ca5512d3d071b2`, response
`gen-1786490261-TMfcJt5jr492iTT2dA6M`, completed with `stop`, one accepted
item, no rejected or ignored proposal, and no deterministic fallback. It used
438 prompt and 89 completion tokens, cost USD 0.0003892, and ran from
2026-08-11T23:17:40.626131+00:00 through
2026-08-11T23:17:43.894060+00:00. This production result resolves the specific
CP-023 plan-output ceiling, but not the overall runtime acceptance gate.

The parallel document/source-integrity call
`modelcall_1acb408e46e5998b`, response
`gen-1786490265-IreIMO88mFsoshGiYAxN`, also completed with `stop`, six accepted
items, no rejected or ignored proposal, and no deterministic fallback. It used
736 prompt and 346 completion tokens, cost USD 0.0011036, and ran from
2026-08-11T23:17:43.910751+00:00 through
2026-08-11T23:17:56.744034+00:00.

Parallel process-decision-mapping call `modelcall_0a572660847e0df6`, response
`gen-1786490266-bA9bYAcZ5u9sx20mRS4t`, returned a complete `stop` response but
failed the strict `model_contribution_majority` boundary under
`AgentBoundaryError`. It retained 20,240 prompt and 1,859 completion tokens,
22,099 total, USD 0.0141842, and 61,943.078 ms latency. Its ledger interval was
2026-08-11T23:17:43.914769+00:00 through
2026-08-11T23:18:45.865871+00:00. The sanitized ledger does not retain
item-level rejection diagnostics for this failed call, so this record does not
infer which proposals missed the boundary.

No later model role or deterministic gate ran. The aggregate is cost-complete
at USD 0.0332561 for 44,585 prompt and 5,030 completion tokens, 49,615 total,
with no unknown-cost call. The full orchestration was rejected and the failed
QA build establishes no current runtime acceptance. The sanitized record is
retained at
`casepath/releases/model-validation-attempt-20260811-12.json`; CP-024 tracks
the unresolved process-decision contribution boundary.

Known aggregate charges for attempts 1, 2, 4, 5, 6, 8, 10, 11, and 12 are USD
0.1634040.
Attempts 3, 7, 9, and 13 remain unknown and excluded rather than treated as zero;
the USD 0.027645 reservations recorded for attempts 7 and 9 remain estimates,
not observed charges.

## Production attempt 13 and external DeepInfra 429

Attempt 13 ran from QA service `srv-d9se2bh42hec73c54sjg`, deploy
`dep-d9ts68ht0dsc73c0nj5g`, against source commit
`690f99e63a6eab4120ad75b83671cffe0f9e62af`. Render records creation at
2026-08-12T00:49:39.049742Z, start at 2026-08-12T00:49:39.025093Z, and
completion at 2026-08-12T00:50:00.690848Z. The public sanitized ledger binds
only canonical-facts call `modelcall_f97afa2a05079468` to orchestration
`orch_bbf7ee808dc04f57`. It failed with `TooManyRequestsResponseError` after
2,777.996 ms and retained no response identity, response model, upstream
provider success metadata, usage, or actual cost.

The signed-in, read-only OpenRouter upstream-request receipt identifies
`gen-1786495797-wwTpDFx93vAismEWwWvY`, final provider DeepInfra, status 429,
exactly one router attempt, and 235 ms router latency. The relevant key had
used approximately 0.6536316% of its USD 25 limit and the account retained
healthy credits. This excludes key/account hard-limit exhaustion from the
bounded classification. The strongest supported attribution is an external
DeepInfra 429 surfaced through OpenRouter; the provider-internal reason for
that 429 remains unknown. No raw provider text is retained.

No canonical result, downstream model role, or deterministic gate was
accepted. Actual cost remains unknown and is excluded from the USD 0.1634040
known aggregate. The failed QA build establishes no current runtime
acceptance. The immutable sanitized record is retained at
`casepath/releases/model-validation-attempt-20260811-13.json`; CP-025 tracks
the external provider availability boundary.

## Production attempt 14, partial known cost, and provider admission boundary

Attempt 14 ran against aligned source commit
`765c610378e7acdc224e200c0e7bbbc65c697c6b`. Frontend deploy
`dep-d9u0ihe417fc73fescgg` and API deploy
`dep-d9u0ihh42hec7398pnm0` were live before QA deploy
`dep-d9u0jnbm8hqs73e7kj3g` accepted run `run_3010703608cef786` at
2026-08-12T05:51:50.213421033Z. The run bound orchestration
`orch_5c8e411d9ccf1b05` and created four network-call ledger records.

Canonical-facts call `modelcall_b5582c002c6f20bb`, response
`gen-1786513914-oQ9RsMSIInmknRyHgohy`, completed with `stop` through DeepInfra.
It retained 18 accepted facts, zero rejected facts, 12 source-reference
projections, 23,188 prompt and 2,050 completion tokens, and USD 0.0160784
actual cost. Orchestrator-plan call `modelcall_47529c6d5a49d7cc`, response
`gen-1786513974-UDX9yxmzmSgZf0S3irqg`, also completed with `stop` through
DeepInfra. It retained one accepted item, no rejected or ignored proposal, 438
prompt and 71 completion tokens, and USD 0.0003496 actual cost.

The logical specialist fan-out then created process-decision call
`modelcall_509e1d20d5f03da7` and document/source-integrity call
`modelcall_17477d1f8a445c6f` 4.051 ms apart. Both failed with
`OpenRouterUpstreamRejectionError` / `provider_upstream_rejection` and provider
error code 429 at the OpenRouter boundary. The route expected DeepInfra, but
neither failed call retained an actual upstream-provider identity, response
identity, usage, or actual cost. It is therefore incorrect to attribute the
failed calls themselves to a proven DeepInfra execution. It is also incorrect
to infer that their close start times caused the 429s; the evidence establishes
only that application-side provider-send overlap was possible.

Known attempt cost is USD 0.016428 for 23,626 prompt and 2,121 completion
tokens. The two failed-call costs remain unknown and excluded. Known aggregate
charges are now USD 0.1798320; attempts 3, 7, 9, and 13 plus the two failed
calls in attempt 14 remain unknown rather than zero. No later model role or
deterministic gate ran. The public QA origin still served a stale prior report
and returned 404 for `evidence-manifest.json`; it supplies no attempt-14
acceptance evidence. The immutable sanitized record and read-only capture
hashes are retained at
`casepath/releases/model-validation-attempt-20260811-14.json`.

The source retains the two specialist entries in `parallel_groups` as logical
DAG fan-out and deterministic join semantics, while physical OpenRouter sends
are now admitted through a process-wide single-flight gate. Both the static
safety contract and dynamic acceptance criteria require
`provider_max_in_flight: 1`. A bounded admission timeout occurs before network
transport and must fail closed as `blocked_provider_concurrency` with
`call_count: 0`, null actual cost, no provider result metadata, and no cacheable
output. This mitigation does not resolve or explain the external 429 condition;
at the Attempt 14 observation, same-commit production acceptance remained
pending.

## Production attempt 15, accepted orchestration, and presentation-identity failure

Attempt 15 ran against aligned source commit
`c030f041566b1b318a030dca85e672717efd489f`. Frontend deploy
`dep-d9u2pg142hec739dtd1g` and API deploy
`dep-d9u2oi6417fc73fjto3g` were live before QA deploy
`dep-d9u2s2bm8hqs73ecqik0` accepted run `run_5f6b88f669bb0316` at
2026-08-12T08:26:06.393323468Z. The run bound orchestration
`orch_47fcf18494e7c1ec`. It made exactly six provider calls under the retained
single-flight runtime cap and was the first retained production attempt whose
application accepted all six required model roles and the three release-owned
deterministic gates. Exact ledger times additionally prove the canonical call
completed before plan creation, the plan completed before both logical
specialist rows were created, both specialists completed before evidence
creation, and evidence completed before final creation. The two specialist
rows remain a logical fan-out; their near-simultaneous record creation is not
misstated as a second physical provider-send overlap.

All six responses used the requested model alias through DeepInfra, completed
with `stop`, and retained complete usage and actual cost. Canonical facts and
evidence checklist succeeded with disclosed guarded fallback; the other four
roles succeeded directly. The ledger totaled 34,988 prompt and 3,669
completion tokens, 38,657 total tokens, and USD 0.0254122 actual cost with no
unknown-cost call. The six call IDs are `modelcall_c64fbe8b2fe28c2d`,
`modelcall_02505ca6820a00f5`, `modelcall_14ab428aed1c371d`,
`modelcall_57134fd6cc869742`, `modelcall_164106a7469fa643`, and
`modelcall_f117ef17925abdbb` in required role order.
Every call row binds orchestration `orch_47fcf18494e7c1ec`. Canonical facts has
no parent; the plan names canonical facts as parent; all four remaining roles
name the plan as parent. Canonical facts retained 17 accepted and one rejected
fact, 10 source-reference projections, and six ignored noncontrolling
normalization proposals. Document/source integrity and process mapping each
retained six accepted, zero rejected, and zero ignored proposals.

The focused browser gate still failed closed. The renderer fell back from
`gate_id` to a terminal event's `validator` field, so validator label
`whole-playbook-validator/15.2` appeared as a fourth `data-gate-id` beside
`deterministic_process_gate`, `deterministic_evidence_gate`, and
`whole_playbook_gate`. The browser did show all six agent identities, the
proof, exact orchestrator label, and exact production boundary. The failed QA
build published no current report or evidence manifest; the public QA origin
continued serving a stale prior report without release identity and returned
404 for the manifest. The immutable sanitized attempt is retained at
`casepath/releases/model-validation-attempt-20260811-15.json`.

This distinction is release-critical: application orchestration was accepted,
but Attempt 15 established no dynamic release acceptance. A passing same-commit report
and hash-bound evidence manifest remain mandatory. Known aggregate actual
charges are now USD 0.2052442; attempts 3, 7, 9, and 13 plus the two failed
calls in attempt 14 remain unknown rather than zero.

## Production attempt 16, exact cache replay, and workspace-capability failure

Attempt 16 ran against aligned source commit
`c325c8a0ec27fe0e3fcec5c24407d7b578df2356`. Frontend deploy
`dep-d9u3gspt0dsc73cftio0` and API deploy `dep-d9u3grlbedkc738nfvn0` were live
before QA deploy `dep-d9u3iinlk1mc73fgfcqg` accepted cold run
`run_67fa8a8b0607c476` and orchestration `orch_b3474368efacacda`. The cold run
accepted the six required model roles and three release-owned deterministic
gates. It also proved the Attempt 15 repair: all six role identities and exactly
three gate identities were visible, while terminal validator
`whole-playbook-validator/15.2` remained a validator and was not promoted to a
fourth gate.

The six cold DeepInfra responses completed with `stop` and retained exact
response, usage, cost, parent, delegation, and orchestration lineage. They
totaled 34,988 prompt and 2,890 completion tokens, 37,878 tokens overall, and
USD 0.0236984 actual cost with no unknown-cost call. Four roles succeeded
directly and canonical facts plus evidence checklist used disclosed guarded
fallback. Warm run `run_5b434ab92b9fe4a6` bound orchestration
`orch_bb0033c34697657c` and then accepted all six roles from cache. Its six
rows each recorded `call_count: 0`, `outcome: cache_hit`, null incremental
actual cost, the exact cold origin call and response identity, and no provider
network call.

The focused browser journey initially rendered the exact three generated
reference patterns in ranked order: `HIST-MOULD-014` rank 1 score 146,
`HIST-MOULD-022` rank 2 score 146, and `HIST-MOULD-009` rank 3 score 136. All
were bound to corpus `generated-reference-patterns/2026-08-12` and context hash
`c54906178181ac68bcb39372362dce664a1f808a8df80f5822a183182db92f59`.
After the QA journey selected the causation/law process node, the process
interaction rerender derived capabilities from stale global stage state and
removed every precedent card. QA therefore rejected the exact ranked-pattern
check. The failed build retained no current report or evidence manifest; the
public QA origin continued serving its 57-check legacy report from commit
`7be18c72f353366930cd5dcace637884e06e63a7` and returned 404 for the manifest.

The immutable sanitized record is
`casepath/releases/model-validation-attempt-20260811-16.json`. It separates
accepted cold application orchestration and accepted warm cache replay from the
failed presentation gate and false runtime-acceptance verdict. Known aggregate
actual charges are now USD 0.2289426. Attempts 3, 7, 9, and 13 plus the two
failed calls in attempt 14 remain unknown rather than zero. The repair stores
the declared evidence/precedent capabilities on each process workspace and
rerenders the clicked workspace from those local values; a new passing
same-commit report and hash-bound evidence manifest remain mandatory.

## Production attempt 17 and evidence-cardinality boundary

Attempt 17 ran against aligned source commit
`580974b0844f3a7e66ba3d324685cd3290798114`. Frontend deploy
`dep-d9u49i7lk1mc73fhl4f0` and API deploy `dep-d9u49ibm8hqs73eg67ug` were live
before QA deploy `dep-d9u4bqjncjis73ag4iag` accepted run
`run_020a11fbd8dc3231` at 2026-08-12T10:07:57.045614253Z. The run bound
orchestration `orch_03c1bbb4a9e4269b`, made exactly five provider calls under
the single-flight cap, and performed no application retry.

Canonical-facts call `modelcall_1a86f535db81984c`, response
`gen-1786529280-uGzNPF2ZCY54LcsTZEbS`, completed directly with 18 accepted
and zero rejected facts, 11 source-reference projections, and one ignored
noncontrolling normalization proposal. It used 23,188 prompt and 2,021
completion tokens and cost USD 0.0160146. Orchestrator-plan call
`modelcall_ef480b12358d325e`, response
`gen-1786529306-pWJvW6D5enjRbiwXKd8Q`, accepted its one bounded contribution
for USD 0.000332. Document/source-integrity call
`modelcall_012b7a5523628d6b`, response
`gen-1786529315-nBI3kJ2WJJyP1RnuoQ2A`, and process-decision-mapping call
`modelcall_9e3ada6a84519278`, response
`gen-1786529312-N1598aWPxvOS8ERprQvw`, each accepted all six bounded
contributions. The deterministic process gate then passed and handed off to
the evidence role.

Evidence-checklist call `modelcall_a91022b32cf47215`, response
`gen-1786529324-2J6kUN6zNOoL7vpGLPFq`, completed with `stop` through
DeepInfra after 1,702.089 ms. It used 3,932 prompt and 11 completion tokens and
cost USD 0.0019646. The sanitized contribution diagnostics retained zero
accepted and 42 rejected fields: both `status` and `artifact_ids` failed the
exact `evidence_contract` for every one of the 21 expected checklist item IDs.
The application therefore raised `AgentBoundaryError` /
`model_contribution_majority` and failed closed. No raw provider output is
retained, so the record does not infer content beyond those bounded
diagnostics.

The deterministic evidence gate, final model role, whole-playbook gate, and
warm replay never started. The five calls total 29,347 prompt and 2,569
completion tokens, 31,916 total tokens, and USD 0.0201973 actual cost with no
unknown-cost call. The failed QA build published no current report or evidence
manifest; the read-only capture at 2026-08-12T10:14:52Z still observed the
57-check legacy report from commit
`7be18c72f353366930cd5dcace637884e06e63a7` and a 404 manifest response.

The immutable sanitized record is
`casepath/releases/model-validation-attempt-20260811-17.json`. Known aggregate
actual charges are now USD 0.2491399. Attempts 3, 7, 9, and 13 plus the two
failed calls in attempt 14 remain unknown rather than zero. The coverage-role
response arrays had admitted empty or partial proposal membership; the evidence
role specifically allowed zero through 21 proposals and did not bind the exact
required item-ID coverage in its bounded payload. Agent-graph `1.2.1` now
requires exact document/process/evidence cardinalities of `6/6/21`, exposes the
required counts and candidate IDs, and rejects missing, duplicate, or unknown
membership before semantic field scoring. Guarded deterministic projection is
retained only for an incorrect field on a returned candidate. A new aligned
production journey remains mandatory to verify that boundary and to establish
dynamic release acceptance.

## Production attempt 18 and document-source output boundary

Attempt 18 ran against aligned source commit
`df4db4872e0854af7dbe97e5c86833ab827a1c1b`. Frontend deploy
`dep-d9u52hmgekts739s8od0` and API deploy `dep-d9u52hu1egvs7396bqo0` were live
before QA deploy `dep-d9u53vjm8hqs73ei6nk0` accepted run
`run_b7e02e168c3217ac` at 2026-08-12T10:59:34.928561247Z. The run bound
orchestration `orch_2ca291c7f62ef75a`, made exactly four provider calls under
the single-flight cap, and performed no application retry.

Canonical-facts call `modelcall_9bd92468cc8f038c`, response
`gen-1786532378-C6etEzhbHwQVX9VzhCWB`, completed directly with 18 accepted and
zero rejected facts, 11 source-reference projections, and one ignored
noncontrolling normalization proposal. It used 23,188 prompt and 2,321
completion tokens and cost USD 0.0166746. Orchestrator-plan call
`modelcall_9a169372b9992d0c`, response
`gen-1786532398-Fq3t3Lh1cWcEQjbJ6XdS`, accepted its one bounded contribution
for USD 0.0003496.

The document/source and process branches then started logically in parallel.
Document/source call `modelcall_4abdccd0ab5d8d6f`, response
`gen-1786532401-OHjtmk6aiCms72NZ62rn`, returned `length` through DeepInfra
after 28,673.821 ms. It used 778 prompt and exactly 4,096 completion tokens and
cost USD 0.0093746. The application rejected it with `AgentBoundaryError` /
`provider_finish_reason` before semantic field scoring or guarded deterministic
projection. Process call `modelcall_179aca2903b5588c`, response
`gen-1786532428-rqSoDh7EoPG9mZJWj7PJ`, had already started and subsequently
completed with six accepted decision-value contributions for `fact_tenancy`,
`fact_dispute`, `fact_recurrence`, `fact_notification`, `fact_cause`, and
`fact_health`. It used 1,147 prompt and 195 completion tokens and cost USD
0.0009769. The process output completed after the document failure, but the
orchestration retained no process-completed receipt and started no deterministic
gate.

The receipt sequence ended at ordinals 16–20: plan started, plan completed,
document started, process started, and document failed. Evidence, final audit,
all three deterministic gates, and warm replay never started. The four calls
total 25,551 prompt and 6,683 completion tokens, 32,234 total tokens, and USD
0.0273757 actual cost with no unknown-cost call. The failed QA build published
no current report or evidence manifest; the read-only capture at
2026-08-12T11:03:29Z still observed the 57-check legacy report from commit
`7be18c72f353366930cd5dcace637884e06e63a7` and a 404 manifest response.

The immutable sanitized record is
`casepath/releases/model-validation-attempt-20260811-18.json`. Known aggregate
actual charges through Attempt 18 are USD 0.2765156. Attempts 3, 7, 9, and 13 plus the two
failed calls in attempt 14 remain unknown rather than zero. Agent-graph `1.2.2`
now gives the document/source role a request-specific finite schema: artifact
IDs are limited to the exact six candidates, source references to at most one
selected text reference, and confidence to integer basis points. Its reasoning
policy is disabled for this bounded copying/classification role with exact wire
policy `effort: none` inside the unchanged 4,096-token total, and cache lineage
binds the prompt, total limit, and reasoning policy. This repair is locally
verified but remains `fixed_unverified` until a new aligned
production journey establishes the dynamic release artifact pair.

## Production attempt 19 and normalized-grounding boundary

Attempt 19 ran against aligned source commit
`72b2527b05e2fc4e25c3b8655d4fe9f2da266580`. QA deploy
`dep-d9u5nhnqj5pc739018eg` accepted cold run `run_7c0b2cd27469bf2e`
with orchestration `orch_8c0994a363e6700c`. All six required model roles
completed through DeepInfra, followed by the deterministic process, evidence,
and whole-playbook gates. Warm run `run_88f6be268fee9a44`, orchestration
`orch_5bb4e7cc4231442d`, then reproduced all six role results through exact
cache-origin bindings and made zero provider calls.

The six cold calls used 35,274 prompt and 3,730 completion tokens, 39,004 total,
and cost USD 0.0256894 with complete billing. Five calls succeeded directly and
the evidence call disclosed guarded deterministic fallback. Focused QA reached
its terminal grounding check, then rejected the journey because the returned
page separated `Tenant` and `Alex Morgan` with a newline while the checked quote
used a space. The values are equivalent after NFKC normalization and whitespace
collapse, but the assertion compared the unnormalized strings.

The browser assertion now applies the shared NFKC and whitespace-collapse
boundary, with focused self-test coverage for newline/space equivalence. The
failed QA build retained neither a current report nor an evidence manifest; its
public origin continued serving the stale 57-check report from source commit
`7be18c72f353366930cd5dcace637884e06e63a7` and returned 404 for the manifest.
Attempt 19 therefore preserves complete cold and warm application evidence but
establishes no dynamic release acceptance. The immutable sanitized record is
`casepath/releases/model-validation-attempt-20260811-19.json`; cumulative known
actual provider charges are USD 0.3022050. CP-037 remains `fixed_unverified`
until a new aligned production journey verifies the normalized-grounding repair
and retains the current report/evidence-manifest pair.

## Production attempt 20 and visual-authority wording boundary

Attempt 20 ran against aligned source commit
`2ab81d4c717c36f86717867230948ffe5c4875f8`. QA deploy
`dep-d9u660fqj5pc73911p2g` accepted cold run
`run_e48f3dfa041155f6` with orchestration
`orch_0ea0187de554be2e`. All six required model roles completed through
DeepInfra, followed by the deterministic process, evidence, and whole-playbook
gates. Warm run `run_2ad603cb2a686137`, orchestration
`orch_1c6bb216c4d5cc63`, then reproduced all six role results through exact
cache-origin bindings and made zero provider calls.

The six cold calls used 35,300 prompt and 3,784 completion tokens, 39,084 total,
and cost USD 0.0258212 with complete billing. Four calls succeeded directly;
canonical facts and evidence checklist disclosed guarded deterministic
fallback. The global frozen ledger contained exactly twelve rows: those six
network calls and the six zero-call cache records.

Focused QA reached its terminal visual-grounding check and then failed
`Visual observation is not rendered as an exact quote`. The renderer was
already correct: it emitted no `<q>` element and displayed
`Hash-bound to these demo image bytes; not machine extraction, model output,
or qualified review.` The assertion additionally required the obsolete phrase
`not an exact quote`, so the wording check failed despite the stronger
authority disclaimer.

The immutable record retains the exact deploy, run, orchestration, twelve-row
ledger, cost/token, gate-progression, terminal-log, readiness, ledger, stale
report, and missing-manifest observations. It does not invent per-gate artifact
hashes: the failed build published no current evidence artifacts, the public
ledger omits gate hashes, and the session-scoped run bodies require an unlogged
random session header. The record is
`casepath/releases/model-validation-attempt-20260811-20.json`; cumulative
known actual provider charges are USD 0.3280262. CP-038 remains
`fixed_unverified` until a new aligned production journey verifies the
visual-authority assertion repair and retains the current
report/evidence-manifest pair.

## Production attempt 21 and collapsed document-row boundary

Attempt 21 ran against aligned source commit
`eb5568a1973f63fdbf0ebd0b3f7cd152c73a29cf`. Frontend deploy
`dep-d9u6mubm8hqs73elmuk0` and API deploy `dep-d9u6msvavr4c73eklnf0`
were live before QA deploy `dep-d9u6okf40ujc73flp1o0` accepted cold run
`run_b33e288771f5734e`, orchestration `orch_41c7d6d772421ec1`. All six
required model roles completed through DeepInfra, followed by the deterministic
process, evidence, and whole-playbook gates. Warm run
`run_57307719ce42f9e9`, orchestration `orch_9189d783e3d07e04`, reproduced
all six role results through exact cache-origin bindings with zero provider
calls.

The six cold calls used 35,274 prompt and 7,165 completion tokens, 42,439 total,
and cost USD 0.0332464 with complete billing. Four calls succeeded directly;
canonical facts and evidence checklist disclosed guarded deterministic
fallback. The frozen global ledger contains exactly twelve rows: six network
calls and six cache hits, with provider maximum in flight one, zero application
retries, zero unknown-cost calls, and complete actual cost.

Focused QA then failed the terminal document-sheet ownership check for
`defect_notice`. The row's data attributes correctly retained primary owner
`notification`, ordered owners `notification,formal_notice`, and current path
`true`, but its enclosing overflow document group remained collapsed. The row
therefore had empty rendered text and no visible secondary relationship copy.
The DTO and canonical ownership projection were correct; the browser assertion
inspected content before making its owning group visible.

The immutable record retains the exact deploy, cold and warm run and
orchestration IDs, twelve ledger rows, cost/token totals, three-gate progression,
terminal assertion, endpoint hashes, and stale public-QA classification. It
truthfully records that per-gate artifact hashes and session-scoped run bodies
were not retained and are unrecoverable after caller cleanup. The failed QA
build published no current report or evidence manifest; its public origin still
served the stale 57-check report for commit
`7be18c72f353366930cd5dcace637884e06e63a7` and returned 404 for the
manifest. The record is
`casepath/releases/model-validation-attempt-20260811-21.json`; cumulative
known actual provider charges are USD 0.3612726. CP-039 remains
`fixed_unverified` until a new aligned production journey verifies the
visibility-first document projection assertion and retains the current
report/evidence-manifest pair.

## Exact dynamic release evidence not yet observed by this record

These point-in-time fields must be supplied by the sanitized ledger and retained
QA artifacts before this deployment can be described as model-backed. They are
not fields to write back into the static release contract:

```text
dynamic_runtime_acceptance_verdict: NOT_ESTABLISHED_BY_THIS_RECORD
historical_model_validation_scope: failed_closed_history_only
failed_attempt_evidence_records: casepath/releases/model-validation-attempt-20260811-01.json through -21.json
failed_attempt_id: authorized-smoke-20260811-01
failed_attempt_application_outcome: rejected
failed_attempt_failure_type: exact_private_reference_mismatch
failed_attempt_successful_ledger_call_bound: false
failed_attempt_accepted_ledger_call_id: null
provider_observed_canonical_model_id: nvidia/nemotron-3-ultra-550b-a55b-20260604
provider_observed_upstream_provider: DeepInfra
provider_observed_actual_cost_usd: 0.00756
provider_observed_prompt_tokens: 3629
provider_observed_completion_tokens: 2625
provider_observed_total_tokens: 6254
provider_observed_finish_reason: stop
latest_failed_attempt_id: production-flagship-20260812-21
latest_failed_attempt_source_commit: eb5568a1973f63fdbf0ebd0b3f7cd152c73a29cf
latest_failed_attempt_frontend_service_id: srv-d9q3ndvavr4c73ao86r0
latest_failed_attempt_frontend_deploy_id: dep-d9u6mubm8hqs73elmuk0
latest_failed_attempt_frontend_deploy_finished_at: 2026-08-12T12:48:14.420369Z
latest_failed_attempt_api_service_id: srv-d9r4v4e417fc73bda92g
latest_failed_attempt_api_deploy_id: dep-d9u6msvavr4c73eklnf0
latest_failed_attempt_api_deploy_finished_at: 2026-08-12T12:49:28.841769Z
latest_failed_attempt_qa_service_id: srv-d9se2bh42hec73c54sjg
latest_failed_attempt_qa_deploy_id: dep-d9u6okf40ujc73flp1o0
latest_failed_attempt_qa_deploy_outcome: build_failed
latest_failed_attempt_qa_deploy_created_at: 2026-08-12T12:51:29.954139Z
latest_failed_attempt_qa_deploy_started_at: 2026-08-12T12:51:29.918727Z
latest_failed_attempt_qa_error_at: 2026-08-12T12:54:37.489228893Z
latest_failed_attempt_qa_build_failed_at: 2026-08-12T12:54:37.531067695Z
latest_failed_attempt_qa_deploy_finished_at: 2026-08-12T12:54:39.158068Z
latest_failed_attempt_run_id: run_b33e288771f5734e
latest_failed_attempt_orchestration_id: orch_41c7d6d772421ec1
latest_failed_attempt_warm_run_id: run_57307719ce42f9e9
latest_failed_attempt_warm_orchestration_id: orch_9189d783e3d07e04
latest_failed_attempt_ledger_created_at: 2026-08-12T12:51:53.812313+00:00
latest_failed_attempt_ledger_updated_at: 2026-08-12T12:53:11.613119+00:00
latest_failed_attempt_application_outcome: accepted
latest_failed_attempt_failure_type: document_sheet_multi_owner_item_not_expanded
latest_failed_attempt_error_type: Error
latest_failed_attempt_error_invariant: document_sheet_multi_owner_item_not_expanded
latest_failed_attempt_full_orchestration_accepted: true
latest_failed_attempt_deterministic_process_gate_started: true
latest_failed_attempt_evidence_checklist_started: true
latest_failed_attempt_final_model_role_started: true
latest_failed_attempt_whole_playbook_gate_started: true
latest_failed_attempt_warm_replay_started: true
latest_failed_attempt_provider_outcome: six_roles_succeeded
latest_failed_attempt_successful_upstream_provider: DeepInfra
latest_failed_attempt_network_call_count: 6
latest_failed_attempt_global_ledger_record_count: 12
latest_failed_attempt_warm_cache_hit_count: 6
latest_failed_attempt_guarded_fallback_call_count: 2
latest_failed_attempt_prompt_tokens: 35274
latest_failed_attempt_completion_tokens: 7165
latest_failed_attempt_total_tokens: 42439
latest_failed_attempt_actual_cost_usd: 0.0332464
latest_failed_attempt_actual_cost_complete: true
latest_failed_attempt_unknown_cost_call_count: 0
latest_failed_attempt_current_report_retained: false
latest_failed_attempt_current_evidence_manifest_retained: false
latest_failed_attempt_deterministic_gate_receipts: 3
latest_failed_attempt_deterministic_gate_ids: deterministic_process_gate, deterministic_evidence_gate, whole_playbook_gate
latest_failed_attempt_gate_artifact_hashes_recoverable: false
latest_failed_attempt_public_qa_classification: stale_previous_deploy_not_attempt_21
latest_failed_attempt_public_qa_report_sha256: 946d6ebd24da538dbf5f7416f93fc27cd653d5dd724015c325b6a845a1cbe425
latest_failed_attempt_public_qa_manifest_http_status: 404
known_failed_attempt_cost_usd_excluding_attempts_03_07_09_13_and_attempt_14_unknown_calls: 0.3612726
logical_specialist_topology: fan_out_and_join
physical_provider_max_in_flight: 1
accepted_retry_status: APPLICATION_ACCEPTED_BUT_QA_REJECTED_AT_COLLAPSED_DOCUMENT_ROW_BOUNDARY_ON_ATTEMPT_21
candidate_source_commit: PENDING
release_id: casepath-v20-reference-20260811
provider: openrouter
requested_model: nvidia/nemotron-3-ultra-550b-a55b
accepted_response_model: PENDING
accepted_upstream_provider: PENDING
accepted_provider_response_id: PENDING
accepted_casepath_call_id: PENDING
accepted_bound_run_id: PENDING
accepted_purpose: PENDING
accepted_prompt_tokens: PENDING
accepted_completion_tokens: PENDING
accepted_total_tokens: PENDING
accepted_actual_cost_usd: PENDING
accepted_latency_ms: PENDING
accepted_cache_key: PENDING
accepted_finish_reason: PENDING
accepted_source_grounding_validation: PENDING
accepted_whole_playbook_validation: PENDING
accepted_retained_evidence_hash: PENDING
```

A configured credential, configured model name, mocked transport response, or
failed-closed provider attempt is insufficient. The observed attempt values
above document failure history only. A deployment is model-backed only when its
passing report and hash-bound evidence manifest prove the six-role cold journey
on the same deployed commit; no source promotion commit follows that verdict.

## Exact pending deployment evidence

These fields must be completed from public identity payloads and retained QA
evidence after the candidate commit is frozen and all three services deploy that
same commit:

```text
deployment_status: PENDING_NOT_DEPLOYED_BY_THIS_RECORD
candidate_source_commit: PENDING
frontend_release_id: PENDING
frontend_source_commit: PENDING
frontend_deployment_identity_hash: PENDING
api_release_id: PENDING
api_source_commit: PENDING
api_health_payload_hash: PENDING
qa_release_id: PENDING
qa_source_commit: PENDING
qa_report_status: PENDING
qa_passed_checks: PENDING
qa_failed_checks: PENDING
qa_report_hash: PENDING
qa_evidence_manifest_hash: PENDING
frontend_deployed_at: PENDING
api_deployed_at: PENDING
qa_executed_at: PENDING
cross_service_alignment: NOT_PROVEN
```

Do not substitute semantic-version equality for source identity. A release is
aligned only when frontend, API, and QA report the same release ID and the same
non-unknown 40-character source commit, and the retained production gate passes.

## Finalization rule

Before describing this convergence candidate as model-backed, deployed, or
aligned, the same-commit dynamic QA report and evidence manifest must pass the
release verifier and remain retained by hash. That runtime verdict does not
modify the static release contract. Expert review, legal approval, operational
validation, and suitability for real claims remain separate evidence gates.

## Local convergence freeze: grounded flagship and causal learning proof

The current source candidate supersedes earlier statements in this document
that described the source manifest, legal registry, visual provenance,
process/evidence joins, precedent ranking, or later-claim learning proof as
mechanically incomplete. Those statements remain useful history, but they are
not the current local-source contract.

The frozen local implementation now provides:

- exact generated-demo visual annotations bound to the observable image SHA-256,
  with no model or pixel-extractor attribution;
- versioned official Swiss-law passages, retrieval scopes, snapshot hashes,
  structured question/source/interpretation/node joins, and explicit pending
  qualified review;
- reciprocal ordered process-to-evidence ownership plus claim-specific exact
  fact, artifact, and status relationships;
- deterministic, hash-bound ranking of exactly three generated reference or
  explicitly governed unverified-memory records;
- a claim/fact/artifact-ID-independent semantic memory eligibility contract;
- one pure five-operation case-specific memory transform, independently bound
  to the accepted review, quarantined candidate, pre-transform boundary, exact
  result receipt, and separately persisted application event;
- a held-out later-demo comparison that revalidates both playbooks, replays the
  transform, exposes the exact nonzero causal delta, and passes ten ordered
  deterministic checks while leaving shared playbook v3 unchanged;
- public knowledge projections that omit review prose and private full-memory
  payloads;
- a backend-enforced counterfactual learning freeze that binds the governed
  memory identity and proves review/memory freeze <= baseline start <= baseline
  completion <= current-run start, so the later comparison cannot be certified
  from a pre-learning exposure;
- a protected-output control that executes the real case-specific memory gate
  against an independently hash-bound pre-review snapshot and recomputes both
  before and after outputs instead of mirroring hashes;
- leakage scans over all twelve observable attachment files and every
  non-schema string in both observable model packages, including parsed email
  subjects; and
- an atomic current-release evidence attestation that joins the live frontend
  identity, live API health identity, passed QA report, exact evidence-manifest
  bytes, retained file inventory, screenshots, and video before enabling the
  public evidence link; and
- a curated 20-file static publish tree containing only the active v20 shell,
  its direct and recursively injected runtime assets, `_headers`, the release
  contract, and a known-commit deployment identity—never legacy executable
  bundles, tools, documentation, release history, or the source manifest; and
- a mandatory paid-call admission gate in the QA build: the exact curated
  commit and an isolated deterministic-reference API must complete the full
  browser lifecycle with a passed temporary report and an empty model ledger
  before the one production browser journey can start. The temporary artifacts
  are deleted and cannot be mistaken for production acceptance evidence; and
- a session-scoped, mutation-aware run-read boundary: the effective
  `X-CasePath-Session` is part of every coalescing key, review POSTs purge
  pre-review reads and wait out same-run read races, and the applied view
  hydrates every reviewed artifact from the same authoritative response instead
  of mixing a cached pre-review graph with a post-review checklist; and
- a stable accessibility boundary: v20 entrance motion is transform-only, Axe
  waits for all finite document animations and two stable paint frames, and a
  bounded failure retains rule IDs, hashed targets, and allowlisted contrast
  diagnostics without rendered claim or free-form failure text.

The local rendered journey completed from flagship analysis through simulated
review, quarantined memory, held-out later claim, visible five-operation receipt,
and 10/10 proof with no browser console warning or error. This is generated-demo
evidence, not qualified review or production model acceptance.

The previous paid-first QA order is retired. `run-definitive-v20.sh` makes the
complete zero-provider browser lifecycle a hard predecessor of production: it
requires the release-pinned Python 3.13.9 runtime, removes provider credentials
from the local API process, rebuilds all ignored runtime documents and images
from tracked deterministic generators and hash-pinned sources, asserts zero ledger
records/network calls/cost after the local journey, and independently requires
an empty production global ledger before caller reset or run creation. It writes
local evidence only to
an isolated temporary directory. A failure in any deterministic downstream UI
state stops the build before a production reset or provider call.

Exact local freeze gates:

```text
backend_tests: 291 passed
release_contract_tests: 114 passed
deployment_and_static_publish_tests: 8 passed
release_tests_total: 122 passed
browser_contract_self_test: 90 fixtures passed
source_manifest_files: 137
release_artifact_files: 25
model_visible_artifact_files: 24
curated_frontend_publish_files: 20
release_leakage_scan: passed
ruff: passed
python_compileall: passed
javascript_syntax: passed
git_diff_check: passed
```

Hosted QA deploy `dep-d9u8a32jobas73ein0kg` on exact commit
`350e834f709ff82e1b79c9f2b9573970c0197ba3` then proved the mandatory
zero-provider boundary and the reviewed-state race repair: it reached the
learning view, failed there inside the 390 px Axe scan, never emitted the
production marker, and left the public ledger at exactly zero records, network
calls, and cost. The failure was the now-repaired transient opacity/contrast
boundary, not a provider or application-orchestration failure. Its replacement
was exercised by zero-provider QA deploy `dep-d9u8srh42hec739rkeo0` on exact
commit `6bb9a63e49d35110730c2e046323a6a43f6727cf`. That replacement again held
the admission boundary: no production marker appeared and the public model
ledger remained exactly empty. Its observed terminal was the 390 px learning
checkpoint, where it exposed a separate, viewport-independent lifecycle defect.
The copy-based continuity matcher read `unverified` as the `verify` stage and
injected a stale, opacity-dimmed process graph under the learning result.
Continuity is now driven only by the structured `evidence`, `experience`, and
`verify` canvas moments, is removed in all other states, and never lowers
opacity on text-bearing process content. Active v17 assets are cache-busted.
The definitive release gate now exercises the full desktop flagship at
1440×900; responsive/mobile website layout is a separate lower-priority surface
and cannot substitute for desktop acceptance. Customer-provided PDFs, email,
photos, source grounding, and evidence inspection remain mandatory throughout
the desktop journey. Exact-commit zero-provider QA deploy
`dep-d9u9m9p42hec739t8pfg` on
`53d1838b072d0a80899d8a6cb724aa704a3f9b1e` passed that continuity boundary
and reached the later result, still without emitting the production marker or
creating any public ledger row. Its strict global locator then found two
`.v17-reuse-thread` sections. The legacy v17 path checked uniqueness before an
await while overlapping enhancement passes were possible; v18 moved the first
thread under a wrapper, allowing a slower direct-sibling insertion guard to
miss it. `renderLaterResult()` now emits the complete
`.v18-reuse-proof > .v17-reuse-thread` synchronously from its authoritative
validated result, receipt, and causal proof. The asynchronous creator and
reparenting path are removed, and the browser plus provider-free behavioral
fixture require exactly one wrapper and thread across applied, retrieved-only,
incomplete, and repeated renders. Zero-provider QA deploy
`dep-d9uaeo61egvs739geq7g` on exact commit
`20e2b5101661945f19dd5a9242878a3fcdca0929` passed that exact topology and
advanced to the returned before/after comparison. It then stopped because the
desktop focus stylesheet hid the correctly rendered `.final-proof` panel, so
the returned result hashes were present only in hidden DOM text. The panel is
now visibly retained and its stylesheet is cache-busted. No production marker
was emitted and the public model ledger remained exactly empty.

The static source and artifact contract is therefore locally verified. At this
source-history freeze, dynamic production acceptance remained unestablished:
attempts 01–21 are failed-closed release history. Attempt 16 accepted the
same-commit six-role, three-gate cold application orchestration and exact
zero-call warm cache replay, but retained no passing current report and
evidence-manifest pair because its process interaction removed the three ranked
precedent cards. Attempt 17 then passed the first four model roles and
deterministic process gate but rejected all 42 evidence fields before the
remaining roles, gates, or warm replay could start. Attempt 18 then completed
canonical facts and planning but rejected the document/source role at its exact
4,096-token ceiling before any deterministic gate; its already-started process
sibling completed without a corresponding completion receipt. Attempt 19
completed all six cold roles and all three deterministic gates, then
replayed all six roles through exact zero-call warm cache lineage before the
terminal browser assertion rejected newline/space-equivalent grounding text.
Attempt 20 then completed the same exact cold and warm topology before the
terminal browser assertion rejected the renderer's stronger visual-authority
copy because it did not contain the obsolete phrase `not an exact quote`.
Attempt 21 again completed the exact cold and warm topology before the terminal
document-sheet assertion read a correct multi-owner row while its enclosing
overflow group was collapsed, leaving its visible text empty. The source-bound
visibility-first document assertion repair remains production-unverified.
A later authoritative same-commit QA artifact pair may supersede that
point-in-time verdict without modifying this historical record.

The following evidence remains external to this local freeze and must not be
inferred from it: qualified expert approval, qualified Swiss-law approval,
independent blind realism review, durable organizational persistence beyond the
demo SQLite deployment, authorization for real claims, and an accepted
same-commit production-model run. The later claim is a known generated fixture
that is temporally held out from the learning step, not a genuinely unseen
external case. Visual observations are curated generated-demo annotations bound
to exact image bytes; the model does not inspect image pixels. The process and
evidence catalog remains a bounded deterministic mould/moisture playbook, and
shared playbook v3 remains unchanged while the one-case memory is unverified and
quarantined.

## Hosted desktop convergence after the local freeze

This section supersedes the point-in-time deployment-status statements above
without rewriting the immutable attempt 01–21 history. The next hosted desktop
journey is frozen as Attempt 22 and ran with frontend, API, and QA aligned on
exact source commit
`0db743a2a7a06c56bd5f011cc5928ef39efe424d`. The browser report completed the
full end-to-end flagship, review, learning, and held-out-later-claim flow with
`218` passed checks and `0` failed checks. The retained production evidence was
exactly 15 JSON documents, 14 PNG screenshots, and one WebM recording. Public
artifact bytes, sizes, SHA-256 values, content types, and no-store headers were
checked against that manifest.

The model topology completed twice cold and twice warm: the flagship produced
six paid calls followed by six exact zero-network cache hits, and the held-out
later claim produced another six paid calls followed by another six exact
cache hits. The immutable final application ledger contained exactly 24 rows,
12 network calls, and 12 cache hits. It was cost complete at USD 0.0459277,
with 58,845 prompt tokens, 7,642 completion tokens, 66,487 total tokens, and
zero unknown-cost calls. This raises the known actual provider-charge total,
including the historical USD 0.3612726, to USD 0.4072003.

The `0db743a` browser pass did not establish the final release verdict because
the verifier published on that same commit rejected valid retained evidence
after its authority had drifted from the backend contracts. The exact root
causes were:

- one global fact ordering in place of claim-specific ordering;
- non-exact required-check handling and a checklist summary that omitted
  secondary owners;
- integer/float JSON representation differences in canonical hashing;
- use of full per-run hashes where the learning proof requires separately
  normalized, model-attribution-stripped semantic hashes;
- an obsolete learning snapshot shape rather than the exact 21-field contract;
  and
- semantic verification of only a selected retained subset rather than every
  manifest-bound JSON document and the complete evidence inventory.

This classification matters: the hosted browser and provider journey passed,
while the release-authority implementation failed closed. The correction makes
the backend-owned claim order, exact required checks, and exact 21-field
learning snapshot shape shared verifier authority. `run-definitive-v20.sh` now
requires the complete deterministic browser output to pass
`verify-runtime-causal-evidence` before the production marker and before any
provider call. That preflight has one exact 27-file inventory: 14 JSON, 12 PNG,
and one WebM. After the one production journey,
`verify-runtime-evidence` requires the exact 30-file production inventory:
15 JSON, 14 PNG, and one WebM. It parses and sanitizes every JSON document;
checks hash, byte size, media type, and PNG/WebM magic; binds deployment,
release, runtime, and readiness identity; validates exact flagship cold-six and
warm-six origin lineage; proves both held-out comparisons use deterministic
application authority with zero model activity; and reconciles the immutable
final 12-row, 6-network, 6-cache ledger. Production
evidence is published only after that full verifier succeeds.

The correction status is `fixed_unverified` until a new hosted run has
frontend, API, and QA on one correction commit and passes both the causal
preflight verifier and the full production verifier. Work on the verifier alone
is not another authorized model attempt, creates no attempt record, and adds no
provider charge.

Attempt 23 on exact commit `9812f961da556c0daad55a6235ebf2f5ddc9a9ee`
passed the 197/0 causal preflight, then made exactly one canonical call under
run `run_34f1c86b5ee01ca8` and orchestration `orch_a6c4d159c78e6a4d`. It
accepted only `fact_date_conflict`, rejected the other exact 17 fact IDs under
`canonical_state`, and stopped before downstream roles, gates, or warm replay.
The call used 23,188 prompt and 4,767 completion tokens and cost USD 0.0220558;
the cumulative known actual cost through Attempt 23 is USD 0.4292561. Public QA
remained the exact atomic Attempt 22 bundle. Immutable history now spans
`model-validation-attempt-20260811-01.json` through `-23.json`.

Attempt 24 on exact commit `a1cc21e77f5c5fb8e1e993044c199eca2655f0f1`
passed the 197/0 zero-provider preflight and causal verifier. Flagship run
`run_ee90220be9719ea4` completed six paid roles and all three deterministic
gates, and isolation run `run_13f7827167f7c7f1` produced six exact zero-call
cache hits. The held-out baseline then started an unnecessary second paid DAG:
its canonical call accepted 16/16 facts, while orchestrator call
`modelcall_b5cbda5d8b277ba3` failed with OpenRouter HTTP 429 and retained no
response identity, usage, or cost. QA waited 900,000 ms before surfacing the
terminal. The immutable boundary is 14 ledger rows, eight network calls, six
cache hits, USD 0.0336607 known cost, and one unknown-cost call. Cumulative
known actual cost through Attempt 24 is USD 0.4629168. Public report and
manifest bytes remained the exact atomic Attempt 22 bundle. Immutable history
now spans `model-validation-attempt-20260811-01.json` through `-24.json`.

CP-047 is closed by Attempt 24's exact 18/18 flagship and 16/16 held-out
canonical acceptance. Canonicalizer `1.7.0`, prompt contract `1.6`, and
canonical schema `1.5` remove deterministic-owned label, state, normalized
value, prose, and process fields from provider judgment. The provider now
contributes only exact `fact_id`, `source_ref_ids`, and `confidence` for the
exact required count and IDs, while strict majority remains bound to real model
contributions. CP-048 tracks the separate unnecessary second paid DAG and slow
terminal timeout. The release contract now limits model acceptance to the
visible flagship, makes the learning comparison deterministic with zero model
activity, pins the final ledger to six cold plus six warm rows, and makes QA
surface a later terminal run failure promptly. This remains `fixed_unverified`
until a new aligned hosted journey passes.

The global sanitized ledger is intentionally immutable for one API instance.
Caller reset preserves it and must never be expanded to erase release history.
Operationally, each candidate receives one fresh API instance/deploy and must
start with an exactly empty ledger. If a provider-bearing run adds rows and a
later gate fails, the next candidate requires another fresh API instance/deploy;
deleting rows, resetting the caller session, or weakening the ledger assertion
is prohibited.

The release target remains the reliable 1440×900 desktop browser product.
Responsive/mobile website work is deferred. This does not defer customer
evidence: customer PDF, email, image, source-grounding, document-inspection,
screenshot, and recording evidence remain mandatory in the desktop journey.

<!-- END CASEPATH IMPLEMENTATION CONVERGENCE RECORD: 2026-08-12 -->
