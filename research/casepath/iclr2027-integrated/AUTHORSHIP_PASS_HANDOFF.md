# Final authorship pass — handed to GPT-6 Pro

**Sent 2026-09-21 to the "Claim AutoPilot" project**, conversation
`https://chatgpt.com/g/g-p-69f1cf906a9881918a05262a1e70e10f-claim-autopilot/c/6ab19bbc-66ac-83eb-875b-db3dfa3f17a5`

## What was sent

| File | Size | What it is |
|---|---|---|
| `casepath_iclr2027_submission.pdf` | 201 KB | the compiled paper at commit `73c6775`, 9 pages of main text |
| `casepath_iclr2027_submission_source.zip` | 114 KB | the complete LaTeX input closure: 35 files, every section, figure and table |
| `RESULT_CONTEXT.md` | 10 KB | every result, what each number means, and what is and is not supported |

`RESULT_CONTEXT.md` is also kept beside this file. Before sending, all 42 of its quantitative
claims were checked against the live generated macros in `numbers.tex`,
`native_final_numbers.tex`, `assessed_state_numbers.tex` and `error_origin_numbers.tex`. All
matched. It is the guardrail for the rewrite: it names the claim boundaries so an editor
optimising for persuasiveness cannot drift past the evidence.

## The brief

A full end-to-end authorship pass: final scientific editor, exposition designer and visual
director. Rewrite, restructure, redraw and simplify around one narrative — important problem,
structural insight, mechanism, precise prediction, decisive experiment, strongest evidence,
mechanistic explanation, practical consequence — so the paper reads as though it was written
around that argument from the first sentence.

Figures to be redrawn from first principles where a clearer explanation exists, with captions and
surrounding prose rewritten together so the figure carries real explanatory load. Exploration via
image generation, final vector figures in Figma, anything quantitative in matplotlib from the data
so values stay exact. Generated raster art must never replace a reproducible quantitative figure.

## Constraints carried into the brief

1. Title and abstract are locked; `submitted_frontmatter.tex` stays verbatim.
2. Main text stays within 9 pages, and is exactly 9 now, so new prose costs prose.
3. Anonymous: no author, employer, agent or own-repository token in any source or PDF metadata.
4. Every number is a generated macro. Numbers are changed by regenerating, never by editing `.tex`.
   `verify_release.py` fails if any macro, table or figure does not reproduce byte for byte.
5. Nothing in the "not supported" lists may be asserted. The two studies are never pooled.

## What the pass was told to foreground

The scope intervention: removing inherited scope makes the controller issue 853 requests to
recover 376 valid ones, against 385 to recover 384 with it, while recall is essentially unchanged
(0.645 against 0.627). Scope does not trade precision for recall; it withdraws demands no active
obligation supported. The compiled-equivalent control matches CasePath exactly, ruling out the
reading that the benefit comes from storing a graph. Alongside it, all 120 unjustified checklist
changes made by the three comparators move documents no branch governs, against 9 for CasePath.

And where the evidence is weaker, each stated once and in proportion: the preregistered
broad-superiority gate failed, and the registered Study B analysis failed on a native interface
mismatch.

## On return

Re-run `python3 research/casepath/verify_release.py`. All eleven checks must pass, including the
9-page limit, byte-for-byte regeneration of every macro, table and figure, anonymity, and the
submission bundle building on its own to the verified PDF.
