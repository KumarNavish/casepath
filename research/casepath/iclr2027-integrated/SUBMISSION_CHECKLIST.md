# ICLR 2027 submission checklist (CasePath)

Deadline: **2026-09-25 23:59 AOE** (paper). Abstract already registered (locked title/abstract in
`submitted_frontmatter.tex`; original Overleaf project `6aac718dca785b22bced2b83` is read-only).

## 1. Files to submit on OpenReview

* **PDF:** `dist/casepath_iclr2027_submission.pdf` (16 pages; main text ends on page 9; statements,
  references and appendices follow). Rebuild after any change: `python3 evidence/build_manuscript_numbers.py`,
  then compile `main.tex`, then refresh `dist/` (zip command in `README.md`).
* **Supplementary zip (anonymous):** the V5 reproducibility archive
  `~/.local/state/navish-acceptance-20260919/final-publication/submitted-foundation/CasePath_ICLR2027_Anonymous_Release_v5.zip`
  (3.2 MB: frozen method pack, benchmark v3 + amendments, predictions, receipts, analysis code, product replay
  verifier) plus, once available, the Study B release (corpus, compiled representation, producer, evaluator,
  `ANALYSIS_CONTRACT.json`, `FINITE_REPORT.json`, execution ledger) and this directory's `evidence/` folder.
  Check the zip for author names before upload (`unzip -l` + `grep -ri` for names, e-mails, hostnames).
* **AI-use disclosure (mandatory form field):** copy the AI Use Statement from `statements.tex`.

## 2. Anonymity checks (done 2026-09-21 12:35 UTC on the current build)

* Sources inputted by `main.tex`: no author names, employer, agent names or repository URLs
  (`grep -i -E "navish|kumar|mobiliar|codex|gpt-6|chatgpt|claude|anthropic|astra|github"`; the only hits are
  the evaluated model alias `openai/gpt-5.6-terra` and the editor name "Ku" inside a reference).
* PDF text (all 16 pages via PDF.js): same result. PDF metadata: Creator "LaTeX with hyperref", no Author.
* Re-run both checks after any edit; do not add `pdfauthor`.

## 3. Page limit

ICLR 2027 author guidelines (fetched 2026-09-21): main text ≤ 9 pages; references, appendices and the
optional ethics / reproducibility statements are excluded; the AI-use statement is excluded. The label
`end-of-main-text` (in `statements.tex`, after the ethics statement) must resolve to page ≤ 9 in `main.aux`.

## 4. Study B (integrated)

Study B is in the paper. Its registered primary analysis failed: every generated artefact failed
native evaluation, all 1,050 cells take adverse penalties and 0 of 12 protected-split practical
targets are met. A separately specified post-hoc analysis of the literal request lists is reported
as a diagnostic, with conservative contrasts negative against all four learned alternatives.

Evidence lives in `evidence/native150/` (7 files, hash-pinned by its own `MANIFEST.json`). Every
Study B number is a macro from `evidence/build_final_native_tables.py` (381 audited macros); it
regenerates identically and `verify_release.py` checks both the hashes and the regeneration.

There is nothing left to integrate. If the evidence is ever revised, re-run that generator, rebuild,
and re-run the verifier.

## 5. Overleaf

Working copy of this manuscript: `https://www.overleaf.com/project/6ab0eea72f79f49c515c7853`. After any
local change, upload the changed files (or the whole `dist/` zip contents) and recompile there; check the
page count matches the local build. Codex's separate project `6ab03c462d2eaea03e194fb2` holds an older draft.

## 6. Before pressing submit

Run `python3 research/casepath/verify_release.py` and confirm every check passes. Its
**Submission bundle** check extracts `dist/casepath_iclr2027_submission_source.zip` into a clean
directory, builds it with no other files present, and requires the result to be byte-identical to the
verified PDF, so the artifact you upload is the artifact that was checked.

* Title and abstract fields identical to `submitted_frontmatter.tex`.
* Primary area / keywords chosen by the author; reciprocal-reviewing and ethics questions answered.
* Final `git status` clean and pushed; `HANDOFF.md` at the repository root current.
