# Read the result, then follow the evidence

Open `http://127.0.0.1:4173/research.html` after starting the local workbench.
The page presents the same authenticated paired-study counts as the paper.
It works without JavaScript, provider credentials or a network connection.

CasePath V5 makes 15 false-positive signed document changes on 27 held-out
pairs, compared with Direct's 27, Graph as context's 41 and Evidence-first's
52. It recovers 24 of 33 required changes; Direct recovers 25 and Graph as
context 31. Thus the result concerns **selectivity with a recall trade-off**.
The frozen broad-superiority gate fails and remains visible beside the result.

## What a signed change measures

A pair differs in one branch-defining fact. An addition is a document present
only after the change; a withdrawal is present only before it. The frozen
scorer selects the best permitted reference realization with a deterministic
tie-break. False positives include both unjustified additions and unjustified
withdrawals. They are not complete-case extra-request counts. Errors common
to both checklists can disappear from this metric.

The nine branch concepts occur in both the nine development pairs and the
27 held-out pairs. This tests new contexts within known rules. It does not
establish unseen-family generalization. F1 intervals resample entire branch
concepts; inference costs exclude preparation and development. Context,
retrieval, call counts and token ceilings differ between these historical arms.

## One measured record, several views

- [Measured summary](../casepath/assets/paired-study-evidence.json): all four
  arms, counts, intervals, charges, failed gates and original evidence hashes.
- [Page generator](../examples/build_research_evidence.py): deterministic
  HTML rendering from that summary; no model or protected-label access.
- [Native comparison](benchmark-and-baselines.md): the separately versioned
  complete-artifact comparison on 150 tenancy claims.
- [Teaching guide](method-guide.md): authored examples of the newer controller.

From the repository root:

```bash
python3 examples/build_research_evidence.py --check
```

To re-export from the authenticated original result and independently summed
receipt metadata, supply their paths:

```bash
python3 examples/build_research_evidence.py \
  --result /path/to/PAIRED_V5_REPRODUCED_RESULT.json \
  --costs /path/to/PAIRED_V5_RECEIPT_ACCOUNTING.json --check
```

The exporter rejects a different original result hash. The summary contains
aggregate historical measurements only; it contains no native150 protected
targets, model credentials or raw claim-level gold records. The page is a
result view, not the complete reproducibility archive.

## Keep implementation correspondence precise

V5 assesses local evidence-rule guards and unions their mapped document routes,
subtracting held document types. Its macrograph does not gate online requests.
The newer native controller adds separate applicability, acquisition permission,
capability-specific adequacy and route selection. Its teaching guide cannot be
used to explain away V5's errors or inherit V5's measured performance.

The original recorded-guard replay matches 72 unit outputs and 36 pair deltas.
It establishes downstream replay correspondence, not fresh model inference,
current native150 parity or hosted deployment identity.

## Complete native corpus: current-case scope intervention

The paper and `research.html` now share the authenticated retrospective report.
On the same 44 completed development cases, both controllers recover 259 valid
requests; inherited domain scope reduces total requests from 592 to 275.
Protected-family reference-chain precision is 0.732 versus 0.318, with a
conservative paired benefit of +0.103. The original registered interface failure,
all unavailable outputs and all seven-arm request contrasts remain preserved.
This is a current-case snapshot comparison of dependent controls, not a new
hidden evaluation or a claim of correct counterfactual branch execution.

`assets/native-study-evidence.json` records all split aggregates, per-family
results, paired contrasts and source hashes. Regenerate both evidence pages
with `python3 examples/build_research_evidence.py`; `--check` verifies the
rendered page and published data against the manuscript's evidence manifest.
The anonymous research archive contains reference targets; the operational
claims workspace continues to load intake inputs only.
