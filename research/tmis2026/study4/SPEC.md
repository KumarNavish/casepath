# Study 4 preparation: specification (planner, 2026-11-12)

Binding for every worker on steps 1 and 2 of `STUDY4_COSTED_PLAN.md`.
Approved by the owner on 2026-11-12: steps 0 to 2, about USD 9 of model
credits in total. Step 1 may spend at most USD 5, step 2 at most USD 4.
Nothing here is a result. Everything produced before the freeze (step 4) is
development material and is labelled so.

## Fixed points

- The artefact under test stays the tested commit (`6a72159c`, worktree
  `/home/user/work/casepath-sync-e`, read-only) until a second design cycle
  is approved. No product change is made in steps 1 and 2.
- Evaluated models: `gpt-6-luna` (cost-efficient) and `gpt-6.1-terra`
  (frontier). No other model is called with credits. Calls go through the
  research harness's caching transport and are recorded in a ledger; a
  worker reports its spend from the ledger.
- Study 3's data (`fresh2/`) are development data from now on. Its stored
  runs, the frozen plan and the registered analysis are never edited.
- Reference answers are used only for scoring. A fix to a prompt or rule
  must be a general rule, never a case-specific patch.
- No assistant or model product name in any file; sessions are named by
  role. No insurer's internal material; public sources only.
- No commits by workers (the planner commits). No git command that changes
  the tree. Secrets are never printed.

## Layout (all under `research/tmis2026/study4/`)

```
SPEC.md                      this file
rules/<regime>/              tenancy | theft | dismissal
  sources/SOURCES.json       every public source: id, title, publisher, URL,
                             retrieved (UTC), sha256 of the stored snapshot,
                             licence note
  sources/<id>.txt           snapshot of the cited articles (statutes) or of
                             the quoted passages only (insurers' conditions)
  rules.json                 the rule set (schema below)
  RULES.md                   the same, readable: one clause per row with its
                             citation and verbatim passage
  rule_text.md               the prose given to every prompt-based design
  workflow/*.json            the same rules in `casepath.workflow/1`,
                             passing the product's `validate_workflow`
  CITATION_CHECK.md          written by a second session (four-eyes)
generator/                   scripts, prompts, README (step 2c)
dev/<regime>/                development files and references (step 2c)
lint/                        planted-defect test (step 2d)
baseline_check/              step 1
```

## Rule sets from public text (step 2a)

Aim: correctness means fidelity to cited public text, which a reader can
check without a jurist.

1. **Sources.** Tenancy and dismissal: the Swiss Code of Obligations (SR
   220) in its official English translation on Fedlex, with the article and
   paragraph numbers; where the translation is unclear the German text
   decides and is quoted beside it. Theft: the Insurance Contract Act (SR
   221.229.1) and the published household-contents conditions already
   collected for Study 1 (the passages in the repository), each with its
   public URL and document date. A source that cannot be fetched or located
   publicly is not used.
2. **A rule** is one of: (a) a *step* of the process with the condition
   under which it is reached; (b) a *document need*: a document, the step it
   belongs to, the condition under which it is needed, and whether it is
   mandatory; (c) a *presumption*: what an unstated fact is taken to be;
   (d) a *stop*: a condition under which the process ends.
3. **Every rule carries** `source_id`, `locator` (article, paragraph,
   letter, or section and page of a conditions document), `passage`
   (verbatim, at most 60 words, found character for character in the stored
   snapshot) and `basis`, one of:
   - `states`: the passage states the rule;
   - `follows`: the rule follows from the passage by a step named in
     `inference` (one sentence);
   - `evidence`: the passage creates a legal condition, and the rule names
     the document that ordinarily proves it; `inference` says why that
     document proves that condition.
   A rule with no passage is not in the rule set. Presumptions and stops
   need a passage too (for instance the burden of proof, Civil Code art. 8,
   or the clause that makes a step depend on an event); if no public text
   supports a presumption, the fact has no presumption and an unstated value
   is unresolved.
4. **Conditions are no broader than the passage.** A condition is worded so
   that it is false in a file to which the passage plainly does not apply.
   Each condition gets a `question` (asked of the file, answerable true,
   false, open or not stated) and a `not_this` line naming the nearest thing
   it does not cover.
5. **Size.** Each regime: 2 or 3 dispute types or claim types, 8 to 14
   documents in the catalogue, 5 to 10 deciding conditions per type
   (including the defining event), at least one stop, at least two
   conditions whose value changes which documents are needed, at least one
   place where two branches reconverge. Close to Study 3's size, so that
   cost per file is comparable.
6. **Schema of `rules.json`:** `{regime, version, sources:[…], types:[{id,
   title, defining_event, facts:[{id, question, not_this, type:"boolean",
   rule:{source_id, locator, passage, basis, inference?}}], steps:[{id,
   title, reached_when, rule}], documents:[{id, title, step, needed_when,
   mandatory, must_show:[…], rule}], presumptions:[{fact, value, applies,
   rule}], stops:[{when, rule}]}]}`. `reached_when` and `needed_when` use the
   condition language of `casepath.workflow/1` (read
   `/home/user/work/casepath-sync-e` for the format and its validator, and
   `harness/product/workflows/fresh-serial-sync/` for examples).
6a. **The intake convention (added 2026-11-12, after the first rule set
   showed that no statute text supports presuming an unmentioned fact
   absent).** Without any presumption every unmentioned fact would be
   unresolved and a handler would be asked about military service and
   pregnancy in every file. That is not how intake works and it would itself
   shape the result. So each regime carries exactly one rule with
   `basis: "convention"`, the same in every regime and given to every design
   in `rule_text.md` in the same words: *a branch fact that the file does not
   mention is taken as not alleged, and the rules are applied as if it were
   absent; the defining event is never presumed: if the file does not mention
   it, it is unresolved; a fact the file raises and leaves unsettled is
   open.* It is declared as a convention of the benchmark, not as law, cites
   no passage, and is listed in `rules.json` under `convention` (not under
   `presumptions`). Presumptions that a passage does support (statutory
   defaults such as the one-month probation period) stay under
   `presumptions` and take precedence. The workflow encodes the convention
   as presumptions with `applies: "unstated"` on every branch fact, each
   pointing to the convention's source entry (`kind: "benchmark_convention"`).
   The study reports results under this convention as primary and, from the
   same stored readings without new model calls where possible, under the
   reading "an unmentioned fact is unresolved" as a sensitivity analysis.
7. **Four-eyes.** A second session, which did not write the rule set, checks
   every rule: passage verbatim in the snapshot; locator right; the rule no
   broader and no narrower than the passage allows under its `basis`;
   `not_this` sensible. It writes `CITATION_CHECK.md` with one line per rule
   (agree / disagree with reason). A rule both do not agree on is removed or
   narrowed until they do; the record of disagreements is kept.

## References (step 2b)

Per regime, two blind evaluator sessions each write an evaluator from
`rule_text.md`, the document catalogue and the designed fact states only, as
in `cleanroom/`. A file's reference is the state of every document: request,
hold (with the fact it waits for), not needed, present and sufficient,
present and insufficient. Files on which the two evaluators differ are
listed; the rule text is corrected at the cited source until they agree, or
the file design is dropped by a stated rule.

## Generator (step 2c)

1. **Designed state.** A seeded script draws, per file: the type; the state
   of every deciding fact from one stated distribution (stated true, stated
   false, open: raised and left unsettled, not mentioned), the defining
   event included; the attachments and whether each is sufficient.
2. **Share sweep.** Files are generated at four levels of the share of files
   with at least one open fact: 0, 10, 25 and 50%. Which fact is open is
   drawn uniformly over the type's deciding facts, the defining event
   included. Files whose defining event is stated false are a fixed 10% of
   every level, flagged, and analysed in their own row.
3. **Writing.** Each design becomes a claim text (150 to 400 words; German
   or English by a stated share; a lay claimant's voice; no legal terms from
   the rule text where a lay person would not use them) written by a session
   of a model family that is not evaluated, working from a bundle that
   contains only the design, a style sheet and the catalogue: no product
   code, no prompts of any design, no rule text beyond the condition
   questions. Attachments are short synthetic documents.
4. **Blind check.** A separate session, given only the text and the
   condition questions, states each fact's state. A text whose recovered
   states differ from the design is rewritten once; if it still differs it
   is dropped and counted.
5. **Scan noise.** A seeded script degrades a fixed 20% of files as a scan
   would: character confusions (rn/m, l/1, O/0), lost diacritics, broken
   lines and hyphenation, a share of dropped characters under 1%. The clean
   text is kept beside the degraded one.
6. **Independence.** Every file has its own story (names, places, dates,
   amounts drawn by the script), so files are independent draws.
7. **Output per file:** design JSON, text, attachments, noise flag, blind-
   check record, reference (from step 2b's evaluator), all hashed in a
   manifest.
8. **Development set now:** 60 files per regime (15 per share level), seed
   recorded. The sealed set is not generated in step 2.

## Lint with planted defects (step 2d)

The lint flags a condition that readings admit as true in at least half of
the files in which the design says it is false or not mentioned (and reports
the rate for every condition). It runs when rules are written; a flag sends
the rule back to its cited passage. Test: for each regime, widen a seeded
third of the conditions to a general circumstance (the widened wording is
written before any run and hashed), read the development files with the
clean and the widened rule set on the cost-efficient model, and report per
condition: planted or not, flagged or not, the rate, and example quotations.
Outcomes: detection rate of planted defects, false-alarm rate on untouched
conditions. One frontier-model arm on one regime if the budget allows.

## Fair-baseline check (step 1)

On Study 3's data. Designs, each written once and hashed before any run on
these data (format checks on three files of the older `fresh/` data only):

- **Prompt with hold option.** One prompt with the same rule text and
  catalogue as Rules in context, plus an explicit three-way decision per
  document (request now; hold with a question when its need depends on a
  fact the file raises and leaves open; do not request) and the same stop
  and silence rules the product's workflow encodes, stated in plain words.
  Both models: three runs on the cost-efficient model, one on the frontier
  model. Tenancy and theft.
- **Model executes rules with hold option** on the frontier model, one run
  (the Study 3 design ran on the cost-efficient model only).

Scored with the registered scorers: strict unsafe errors and all deviations
per claim (tenancy), wrong + missed changes per pair and the unresolved-pair
measures (theft), by the registered subsets and by the stated/open split.
Paired per-case contrasts against CasePath on the same model (the frontier
comparison uses the stored checklist-only run), sign-flip p, labelled post
hoc. Report what the hold-capable designs do on files that state every
fact, on open branch facts, and on denied and open defining events.
