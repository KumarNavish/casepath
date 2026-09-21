# CasePath — ICLR 2027 submission source

This directory is the submission manuscript for **"CasePath: An Agentic, Process-First Architecture for
Determining Evidence Requirements"** (title and abstract preserved verbatim from the registered submission in
`submitted_frontmatter.tex`).

## Build

```bash
SOURCE_DATE_EPOCH=1789948800 ../../../.runtime/tools/tectonic/tectonic main.tex
```

Tectonic 0.17 (XeTeX); any XeLaTeX/pdfLaTeX with BibTeX also works. Pinning `SOURCE_DATE_EPOCH`
makes the build byte-reproducible, so a rebuild of an unchanged source tree reproduces
`main.pdf` exactly; `verify_release.py` checks that.

16 pages: main text ends on page 9 (`\label{end-of-main-text}` in `statements.tex` records the page in
`main.aux`); the ethics, reproducibility and AI-use statements, references and appendices follow and are
excluded from the ICLR page limit. `dist/` holds the Overleaf-ready source zip and the compiled PDF.

## Every number is generated

No number in the prose or tables is typed by hand.

* `evidence/build_manuscript_numbers.py` regenerates `numbers.tex` (all macros) and the five tables
  (`table_main_results.tex`, `table_claim_gates.tex`, `table_family_results.tex`, `table_costs.tex`,
  `table_native_execution.tex`) from the evidence files in `evidence/` and writes
  `evidence/NUMERICAL_AUDIT.json` (macro → value → evidence file SHA-256 → JSON pointer).
* `evidence/check_literal_numbers.py` lists any literal number left in the prose.
* `evidence/CITATION_VERIFICATION.json` records how every cited key in `references.bib` was verified
  (arXiv id, DOI, PMLR listing or reachable URL).

Evidence provenance: Study A files (`PAIRED_V5_REPRODUCED_RESULT.json`, `PAIRED_V5_RECEIPT_ACCOUNTING.json`,
`PAIRED_V5_REPRODUCED_PARITY.json`, `SHORTCUT_PREFLIGHT_V3.json`, `HISTORICAL_AUDIT.json`) are the
authenticated reproduction of the frozen V5 paired-intervention study; `PUBLICATION_STATIC_FACTS.json` and
`ANALYSIS_CONTRACT.json` are the frozen Study B design and analysis contract; `studyB_execution_status.json`
is a target-free snapshot of recorded Study B cells (execution status only, no scores).

## One-command verification

`python3 ../verify_release.py` runs every offline check and prints one table: Study A reproduces,
the explorer marks sum to the report, regenerating the macros leaves the committed files unchanged,
no number is hand-typed, every recomputable macro matches a fresh recomputation, the paper builds
with its main text ending on page 9 or earlier, and the sources and PDF carry no identifying token.
It exits non-zero if any check fails and reports a check whose inputs are absent as "not present".

## Cross-check against the released benchmark

`evidence/check_against_benchmark_release.py` reruns the frozen analysis in
[`../branch-benchmark/`](../branch-benchmark/README.md) on the recorded predictions and confirms
that every macro traceable to the held-out report, the shortcut preflight or the product-parity
report equals the freshly recomputed value (86 macros at the time of writing). Macros that come
from design or accounting records are reported as having no recomputation path rather than as
passing.

## Study B results (pending)

Scoring of the 150-claim study is contractually deferred until both prediction phases are frozen, so the
paper reports the protocol and the completed development-split execution record. When the frozen analysis
code produces `FINITE_REPORT.json` (schema `casepath.finite-corpus-descriptive/1.0.0`):

```bash
python3 evidence/build_native_results.py /path/to/FINITE_REPORT.json
```

writes `native_results_numbers.tex`, `table_native_results.tex` and `evidence/NATIVE_RESULTS_AUDIT.json`;
then add `\input{native_results_numbers.tex}` to `main.tex`, write the results paragraph in
`native_study.tex` from the generated macros only, recompile and re-run the two check scripts.

## Layout

`main.tex` → `submitted_frontmatter` → `introduction` → `method` → `benchmark` → `paired_results` →
`native_study` → `related` → `release` → `discussion` (limitations, conclusion) → `statements` → references →
`appendix_studya` → `appendix_native`. Files inherited from earlier assemblies that `main.tex` does not input
(`studies.tex`, `related_product.tex`, `table_correspondence.tex`, `technical_correspondence.tex`) are kept
for history only.
