# Data card: 150 synthetic intake claims

CasePath ships the **original observable intake packets** used in the complete-corpus study. They are fictional claims about Swiss tenancy matters, intended for process and evidence-planning research and local product inspection. They are not real customer records.

| Item | Released content |
| --- | ---: |
| Claims | 150 |
| Languages | 75 English; 75 Swiss Standard German |
| Customer communications | 150 |
| Claims with no attachment | 105 |
| Claims with one attachment | 33 |
| Claims with two attachments | 12 |
| Attachments | 47 PDFs; 10 JPEGs |
| Bound files, including registries and static policy | 660 |

The study groups the claims into 28 scenario families across three tenancy domains. Its development portion contains 60 claims in 11 families; the protected-family portion contains 90 claims in 17 families. The operational packet contains **inputs**, not the reference labels or selected paths. The [study protocol](benchmark-and-baselines.md) defines the split and the [anonymous reproduction archive](../research/casepath/iclr2027-integrated/README.md) contains the licensed reference material. All 150 observable inputs have since been inspected in product work, so the protected-family label no longer means untouched input exposure.

## What one claim contains

Open [this claim with two termination notices](http://127.0.0.1:4173/#claim=clm_f69b1747447bc221) after starting the local app. The packet binds one customer message and two PDF attachments. It also has an immutable source registry and the same static policy template used by the other claims. The message reports conflicting dates; the product must inspect the notices and keep unresolved details unresolved.

The files live under `casepath-api/casepath_api/corpora/synthetic-150/`:

| Path | Purpose |
| --- | --- |
| `manifest.json` | Corpus roster, claim bindings, file hashes, language, time, and media type. |
| `claims/<claim-id>.json` | Observable message, attachment references, and intake metadata. |
| `artifacts/<claim-id>/` | Original customer communication and attachments, plus bounded text projection. |
| `registries/<claim-id>.json` | Source identity and locator records for the claim. |
| `policy/` | Shared static rule templates and authority passages. |
| `LICENSE-DATA` | CC BY 4.0 license. |

The claim object declares itself an `intake-only/1.2.0` downstream input. It contains no post-intake outcome. The corpus manifest records `contains_expected_outputs: false` and `contains_sealed_targets: false`. Do not infer a correct decision from a filename, subject, or customer statement.

## Load and verify

`./bin/casepath prepare` checks the sealed source tree. Starting `./bin/casepath dev` also validates the bound corpus and source identities before serving claims. For direct read-only access after preparation:

```sh
PYTHONPATH=casepath-api .runtime/casepath-dev-v2/venv/bin/python -B - <<'PY'
from pathlib import Path
from casepath_api.workspace_corpus import PublicCorpus

corpus = PublicCorpus(Path("casepath-api/casepath_api/corpora/synthetic-150"))
claim = corpus.claim("clm_f69b1747447bc221")
print(len(corpus.bindings), len(claim["attachments"]))  # 150 2
PY
```

The corpus manifest's canonical **payload** digest is `921e7ce79ecb3ee7811b6ee2530b4f6dc5c302da3ade6afbdae0b92fd822790e`. Its file SHA-256 is `7c885d3fd112dfc7314719d661fa73449f72b7bdf5b83159da9fa3e0b9a1b7eb`; these differ because the file includes the payload digest field. The bound source-manifest file digest is `638630886a1d291dfe9009839eb0519130e56700bb4d454277ce2e45c6044f4c`. The older `synthetic-dev-60` corpus remains unchanged for regression tests.

## Intended use and limits

Use these packets to inspect the product, test source-grounded process and evidence interfaces, or reproduce the finite-corpus comparison with the separate evaluator. The cases are synthetic and are not evidence of legal correctness, expert agreement, customer outcomes, or production safety. Message phrasing and attachment availability vary, but the packet does not contain a real acquisition trajectory. The original evaluated bytes and claim identifiers are frozen; presentation improvements must use derived views rather than editing the corpus.
