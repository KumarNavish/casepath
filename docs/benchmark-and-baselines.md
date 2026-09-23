# What the comparison tests

The [paired V5 study](research-evidence.md) supplies a separate, already measured
branch-change result. The comparison below uses a different controller,
population and endpoint; the two results must not be pooled.

The native-150 study asks whether explicit obligation execution changes the
quality of document planning when every learned pipeline receives the same
public knowledge and observable case packet. The corpus contains 150 synthetic
cases in 28 families across three Swiss tenancy domains: 60 development cases
in 11 families and 90 protected-split cases in 17 families.

All observable inputs have previously been inspected during product work.
Historical semantic-target exposure is unknown. The protected split must not be
described as untouched-input confirmation. This study is a finite-corpus
comparison of complete pipelines with a shared deterministic compilation.

## Read the alternatives as distinct operations

| Condition | What the model produces | How requests are obtained |
|---|---|---|
| CasePath | Complete state assessment, followed by review | The obligation controller derives demands from the assessed state. |
| Direct | Complete native process/evidence artifact, followed by review | The model selects the requests directly, without an imposed reasoning order. |
| Document-first | Document needs and states, then the complete native artifact | The model reviews its document-led draft against the same sources. |
| Process-context | Process scope and obligations, then the complete native artifact | The model selects requests using that context. |
| Rule-first | Condition/action rules, then the complete native artifact | The model executes and reviews its inferred rules. |
| Compiled equivalent | Reuses the CasePath assessment | Equivalent compiled conditions replace graph evaluation; no independent model sample. |
| Local-scope ablation | Reuses the CasePath assessment | Removes inherited applicability by clearing parent scopes; preserves local guards, acquisition, adequacy and route rules. |

The learned conditions are custom, resource-matched implementations. Rule-first
is neither a reproduction of a named published system nor the unavailable
historical template kernel. Conceptual precedents must be cited as related work,
not presented as evaluated implementations.

The exact arm instructions and configuration are in
[the compact schedule](../casepath-api/casepath_api/obligation_control/study_v1/compact_v3/schedule.py).
The [runner](../casepath-api/casepath_api/obligation_control/study_v1/compact_v3/runner.py)
preserves failed outputs and their dependent consequences.

For the surrounding literature, see [sources and related benchmarks](research-sources.md).
Those works provide context; they are not additional evaluated conditions.

## What is held in common

Each learned condition receives the same observable packet, authoritative source
material, public templates, ontology and retrieval projection. Each has two
sequential draft/review calls, one sample, medium reasoning and a 4,096-token
completion limit per call. Web access and tools are disabled. Temperature is
omitted, so its effective default is unknown. The requested model alias is
`openai/gpt-5.6-terra`; generation records identify
`openai/gpt-5.6-terra-20260709`. The underlying checkpoint is not independently
attested by those records.

The full planning object and its native projection are different artifacts.
The native projection loses some planning detail; evaluate actual immediate
requests separately from native conditional requests resolved against a
reference scenario.

## How to interpret the final measurements

Report development, protected-split and all-case results with stable
denominators, all originating and dependent failures, and actual resource cost.
Aggregate cases within families, families within domains, then the three domains
equally. A missing reference endpoint stays unavailable. Family-deletion ranges
describe corpus-composition sensitivity, not confidence intervals or population
uncertainty. The compiled and ablated controls are paired, dependent outputs.

All 1,050 primary prediction cells were saved, but the registered native
evaluation failed at its graph interface. Its adverse penalties remain in the
release. The paper reports separate request-only and current-case analyses;
neither is a successful registered evaluation. In the current-case scope
intervention, full and local-only controllers reuse the same saved assessment.
On 44 completed development cases, both recover 259 valid requests; inherited
scope reduces total requests from 592 to 275. See [the evidence record](research-evidence.md)
for protected-family results, unavailable outputs, costs and provenance. The
paper, repository and app result views use that same authenticated record.
