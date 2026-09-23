# CasePath: process-first evidence planning

The manuscript develops one dependency: a document is required because it can
establish a fact needed by an active obligation. The submitted title and abstract
are preserved in `submitted_frontmatter.tex`.

Study A tests the signed checklist change caused by one changed case fact. Study B
uses all 150 released claims and separates native graph conformance from a
post-hoc diagnostic of literal requests and a separately specified current-case
scope intervention. The paper, tables and figures preserve those distinctions.

## Read and build

`dist/casepath_iclr2027_submission.pdf` contains the anonymous paper, references
and supplement. `dist/casepath_iclr2027_submission_source.zip` builds independently
in Overleaf with XeLaTeX, or locally with Tectonic:

```sh
SOURCE_DATE_EPOCH=1789948800 tectonic main.tex
```

The main-text boundary is marked before the reproducibility, ethics and AI-use
statements. The release verifier checks the nine-page main-text limit, unresolved
references, overflowing boxes and anonymity. A clean extraction of the source
archive must build to the same PDF under the recorded Tectonic build.

## Reproduce the figures and tables

```sh
python3 evidence/build_manuscript_numbers.py
python3 evidence/build_final_native_tables.py
python3 evidence/build_assessed_state_tables.py
python3 evidence/build_error_origin_numbers.py
python3 evidence/build_figures.py
```

The figure generator needs Matplotlib. The LaTeX build uses the supplied PDFs and
does not require plotting software. The four figures are a teaching schematic,
Study A's measured family behavior, the retrospective current-case scope comparison, and a
recorded development case. Their provenance is recorded in `evidence/FIGURE_AUDIT.json`.

`evidence/NUMERICAL_AUDIT.json` and `evidence/NATIVE_FINAL_NUMERICAL_AUDIT.json`
map numerical macros to values, source hashes and JSON pointers.
`evidence/ASSESSED_STATE_NUMERICAL_AUDIT.json` and
`evidence/ERROR_ORIGIN_NUMERICAL_AUDIT.json` do the same for the
separate current-case and descriptive error-origin analyses. The native
reports and their manifest are in `evidence/native150/`. These files include
the registered primary failure, separate request diagnostic and current-case
analysis. The scope intervention increases protected-family reference-chain
precision from 0.318 to 0.732; the conservative paired benefit is +0.103.
It does not establish counterfactual branch correctness or exact-source entailment.
`evidence/CITATION_VERIFICATION.json` records the checked bibliography metadata.

## Reproduce the measurements

The companion `dist/casepath_iclr2027_reproducibility.zip` contains the original
method, source snapshots, licensed exact reference containers, all prediction
and failure cells, provider usage, native evaluator and offline replay commands.
Its README explains the separate Study A and Study B commands. No provider calls
are needed. The archive manifest verifies every file; the exact-replay receipt
binds the reproduced reports to those used in this manuscript.

From the repository root, run:

```sh
python3 research/casepath/verify_release.py
```

Install Tectonic, Matplotlib and SciencePlots for the complete build. If Tectonic is outside `PATH`, set `CASEPATH_TECTONIC` to its executable. The historical figure generator uses an isolated Matplotlib configuration so personal plotting defaults cannot change the released PDF bytes.

This recomputes Study A, checks all generated publication artifacts, compiles the
paper and a clean source extraction, and checks the full reproduction archive
against its manifest and recorded exact native-replay receipt. It does not launch
new inference or repeat native scoring.

## Measurement boundaries

Study A evaluates known branch concepts in held-out contexts, with unequal
computation across pipelines. Study B fixes shared knowledge and call budgets;
its protected-family label records the original target boundary, not untouched
observable inputs. Those targets are now released. The primary graph-interface
failure, unavailable outputs and negative conservative paired contrasts remain
part of the evidence. Request-list agreement is not native contract acceptance.

Files not reached from `main.tex` are historical sources; only the actual input
closure is included in the submission source archive.
