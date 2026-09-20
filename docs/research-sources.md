# Sources, benchmarks and comparison provenance

Every comparison needs an exact identity. The native-150 experiment uses
CasePath's release corpus and native evaluator. Its five learned conditions are
custom implementations defined in
[the executed schedule](../casepath-api/casepath_api/obligation_control/study_v1/compact_v3/schedule.py),
with two [dependent controls](../casepath-api/casepath_api/obligation_control/study_v1/adapters.py).
They are not reproductions of the papers below.

The corpus is this work's dataset: cite its dataset section, release version,
source manifests and evaluator alongside the final paper. Do not assign it an
external benchmark's citation or an unregistered DOI. Original legal and
procedural sources must be cited through their exact source registry records;
a later webpage is not a substitute for the snapshot supplied to a model.

## Read the closest ideas first

| Work | What to read it for | Relation to this comparison |
|---|---|---|
| [Kim, *Evidence-Obligation Pool-Gated Retrieval* (2026)](https://www.preprints.org/manuscript/202607.1060) | Conditional evidence obligations, a ledger and warrant judgments | A close conceptual predecessor; a non-peer-reviewed preprint, not an evaluated baseline here. |
| [Yu et al., *Compile, Then Page* (2026), v3](https://arxiv.org/abs/2607.11346v3) | Compiled SOP programs and a capability-gated runtime | Related procedural control; not a reproduced implementation here. |
| [Xiao et al., *FlowBench* (2024)](https://aclanthology.org/2024.findings-emnlp.638/) | Workflow-guided planning and alternative workflow representations | A neighboring evaluation task; no current-method FlowBench score is claimed. |
| [Qiao et al., *Benchmarking Agentic Workflow Generation* (2024 preprint)](https://arxiv.org/abs/2410.07869) | WorFBench and sequence/subgraph-based workflow evaluation | A neighboring graph-evaluation object; CasePath's native scorer is separate. |
| [Du et al., *PAGED* (2024)](https://aclanthology.org/2024.acl-long.583/) | Procedural graph extraction from documents | Named in the original corpus manifest for earlier discovery evidence; no transfer score for the current method is claimed. |
| [Dhuliawala et al., *Chain-of-Verification* (2024)](https://aclanthology.org/2024.findings-acl.212/) | Drafting, independent verification and revision | Review is an established idea; CasePath's two-call review is not a CoVe reproduction. |

Full attributable records are in [the bibliography](research-references.bib).
The bibliography is shared with the paper's working citation inventory. A
citation supports the operation actually described; it does not establish that
CasePath reproduced the cited method or transferred to the cited benchmark.

## Keep mechanism and evidence separate

The [interactive guide](method-guide.md) demonstrates deterministic semantics on
authored teaching states. The native-150 study measures complete pipeline
behavior on the released corpus. A model receipt identifies an actual invocation;
a successful UI test establishes an interaction; a native evaluation establishes
only the endpoints and population it scores. These are complementary records,
with different claims.

The final numerical audit must connect each reported value to the exact result
field, split, denominator, weighting, failure treatment and source digest. The
same record should generate manuscript tables, public result summaries and app
comparison views.
