# Sources, benchmarks and comparison provenance

The paired V5 study and the complete native150 comparison use custom comparison
conditions. The works below establish antecedents and neighboring tasks; none is
an additional executed benchmark or a reproduced baseline in these studies.

| Primary source | Operation supported | Evidence role |
|---|---|---|
| [Evidence-Obligation Pool-Gated Retrieval: Stable Multi-Cycle Retrieval via Evidence Ledger and Warrant Judge (2026)](https://www.preprints.org/manuscript/202607.1060) | Conditional evidence obligations, a turn-scoped ledger and semantic warrant judgments govern retrieval and finalization. | Sections 4.2–4.4, 5 and 6; preprint, not peer reviewed. |
| [Compile, Then Page: Executable SOP Programs and a Capability-Gated Runtime for Procedural LLM Agents (2026)](https://arxiv.org/html/2607.11346v3) | Deterministic compilation of SOP constraints into executable procedures, evidence-bearing returns and a runtime that exposes the active frame. | Version 3; method/runtime description. Soft enforcement is not a proof guarantee. |
| [FlowBench: Revisiting and Benchmarking Workflow-Guided Planning for LLM-based Agents (2024)](https://aclanthology.org/2024.findings-emnlp.638/) | Workflow-guided planning is evaluated across workflow-knowledge formats. | Official ACL Anthology abstract and paper. |
| [Benchmarking Agentic Workflow Generation (2025)](https://arxiv.org/abs/2410.07869v3) | WorFBench evaluates workflow generation using sequence and graph matching. | Version 3, February 23, 2025; initially posted 2024. |
| [PAGED: A Benchmark for Procedural Graphs Extraction from Documents (2024)](https://aclanthology.org/2024.acl-long.583/) | PAGED evaluates extraction of procedural graphs from documents. | Official ACL Anthology publication and metadata. |
| [ReAct: Synergizing Reasoning and Acting in Language Models (2023)](https://arxiv.org/abs/2210.03629) | ReAct interleaves reasoning and actions. | Primary preprint; not the no-tools comparator implementation. |
| [Chain-of-Verification Reduces Hallucination in Large Language Models (2024)](https://aclanthology.org/2024.findings-acl.212/) | Chain-of-Verification generates a draft, plans verification questions, independently answers them and revises. | Official ACL Anthology; our two-call review does not reproduce this four-step procedure. |
| [Case Management Model and Notation (CMMN), Version 1.1 (2016)](https://www.omg.org/spec/CMMN/1.1) | CMMN 1.1 defines case management models with case state and conditions. | Specification, December 2016; not a comparative evidence-planning evaluation. |
| [Decision Model and Notation (DMN), Version 1.5 (2024)](https://www.omg.org/spec/DMN/1.5) | DMN 1.5 standardizes decision models and decision tables. | Specification, August 2024; no claim that CasePath invented executable decisions. |
| [LegalRuleML Core Specification Version 1.0 (2021)](https://docs.oasis-open.org/legalruleml/legalruleml-core-spec/v1.0/os/legalruleml-core-spec-v1.0-os.html) | LegalRuleML represents normative rules, deontic operators, alternatives and source associations. | OASIS Standard, 30 August 2021; sections 4.2 and 4.3. |
| [Catala: A Programming Language for the Law (2021)](https://arxiv.org/abs/2103.03198) | Catala is a programming language for translating legislative rules into executable code. | Primary preprint v2 and DOI 10.1145/3473582; authored formalization, not automatic legal truth. |
| [Teaching Language Models to Support Answers with Verified Quotes (2022)](https://arxiv.org/abs/2203.11147) | Verified source quotations support answers that readers can inspect. | Exact quotation establishes textual provenance, not semantic entailment by itself. |
| [GraphCompliance: Aligning Policy and Context Graphs for LLM-Based Regulatory Compliance (2025)](https://arxiv.org/abs/2510.26309) | GraphCompliance aligns policy and context graphs for regulatory compliance assessment. | Primary abstract; do not describe it as procedural graph extraction. |
| [InfoGatherer: Principled Information Seeking via Evidence Retrieval and Strategic Questioning (2026)](https://arxiv.org/abs/2603.05909) | InfoGatherer combines retrieval and targeted questions using belief assignments over an evidential network. | Primary v1 abstract; legal and medical tasks; not a CasePath reproduction. |
| [CLER: A Benchmark for Chinese Litigation Evidence Reasoning (2026)](https://www.sciencedirect.com/science/article/pii/S0306457326000592) | CLER evaluates structured evidence lists and the legal facts they support from claims and factual premises. | Publisher abstract, introduction and dataset analysis; DOI 10.1016/j.ipm.2026.104667. |
| [Add a Document List Definition to a Service Definition (2026)](https://www.servicenow.com/docs/r/financial-services-operations/insurance-claims/add-document-list-definition-to-service-definition.html) | Insurance-claim decision tables associate service definitions with document lists and create verification tasks. | Official Australia documentation updated 12 March 2026; industrial antecedent, not experimental comparator. |

Full author, title, venue, version and identifier records are in
[the shared paper bibliography](research-references.bib). This file is byte-identical
to the current manuscript bibliography.

The corpus is this work’s dataset. Cite its version, source manifests and native
evaluator with the paper; do not assign it a different benchmark’s citation or an
unregistered DOI. Original legal and procedural sources are identified by their
exact preserved passage/version records. A current web page is not a substitute
for the actual snapshot supplied to a model.

Read the [paired result](research-evidence.md), [native comparison definitions](benchmark-and-baselines.md)
and [teaching guide](method-guide.md) separately. The same original result hash
binds the paper’s paired figure and table to the app’s measured comparison.
Native150 performance is added only from its completed authenticated evaluation.
