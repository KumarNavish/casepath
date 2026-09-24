# CasePath household-theft case pairs (Study A)

36 pairs of synthetic household-theft claims. The two cases of a pair
differ in one sentence, and that sentence decides a branch of the claims
process; the reference says which documents the change justifies, according to
real policy terms and law. This is the dataset of Study A in the paper
*CasePath: An Agentic, Process-First Architecture for Determining Evidence
Requirements*. It is released for developing and evaluating agents that must
change their requests exactly where a fact changes, and nowhere else.

Data: CC BY 4.0 (`LICENSE-DATA`), except the quoted source passages (see
`SOURCES.md`). Code: Apache 2.0 (`LICENSE-CODE`).

## What a pair contains

- **Two case texts** (`benchmark/benchmark/BENCHMARK_V3.json`, `units`): a short
  English claim story, followed by nine statements about the branch conditions.
  In the "off" case all nine conditions are off; in the "on" case one of them is
  on. For example, "No stolen item is separately scheduled in the policy with an
  insured value of CHF 1,000 or more" becomes "A stolen watch is separately
  scheduled in the policy with an insured value of CHF 4,000." Everything else
  is identical.
- **The reference** (`pairs`): the documents to add or withdraw between the two
  checklists, grouped into requirements. Where the sources accept alternatives,
  every acceptable combination is listed (`acceptable_signed_deltas`); asking
  for both alternatives when one suffices counts as a wrong change.
- **The shared inputs** every method receives: 197 verbatim passages from law,
  policy terms, a claim form and model conditions
  (`benchmark/benchmark/SOURCE_SNAPSHOT_V2.json`), and a catalogue of the 33
  document types those sources name (`benchmark/benchmark/FULL_CATALOGUE.json`).

Each case also has nine labelled condition states, fixed by construction, which
gives 648 labelled states in all.

## Where things are

```
benchmark/                  the Study A benchmark exactly as evaluated
  benchmark/                cases, pairs, references, amendments, sources, catalogue
  predictions/              the recorded checklists of the four methods in the paper
  analysis/ expected/       the frozen scorer and the preserved reports
  reproduce.py              recomputes every Study A number offline
  explore.html              browse the held-out pairs and every method's changes
reference-contract/         the contract the references are derived from
representation/             CasePath's frozen, model-extracted statements and rules
construction/               the scripts that generated the cases and derived the references
SOURCES.md, sources/        the seven source documents, citations and passage attribution
verify.py                   checks the evaluated files against recorded hashes
```

## Composition

| | |
|---|---|
| Pairs | 36: 9 development, 27 held out |
| Cases | 72 (40 distinct texts: within a story, the nine "off" cases are identical) |
| Branch conditions | 9, in three groups: stolen property; events after the claim; settlement and recourse |
| Stories | 4 claim settings; the first is the development split |
| Case text | English, 141 to 155 words |
| Required changes | 44 (11 development, 33 held out), all additions |
| Alternatives | one requirement (receipt or expert valuation), in 4 pairs |
| Source passages | 197, from 7 documents (`SOURCES.md`) |
| Document catalogue | 33 types, all named in the sources |
| Recorded outputs | 4 methods, full before-and-after checklists for all 36 pairs |
| CasePath's representation | 308 extracted statements, 98 evidence rules, 87 case conditions, 13 statements needing no evidence |

## Using it

```
python3 benchmark/reproduce.py      # recomputes the Study A results, about seven seconds
python3 verify.py                   # checks the evaluated files against recorded hashes
```

- **Develop** on the 9 development pairs (the first story of each condition).
- **Evaluate** on the 27 held-out pairs, scoring the signed change between the
  two checklists with the frozen scorer. A constant answer scores zero: the best
  fixed change learned on eight conditions scores an F1 of 0.0 on the ninth.
- **Compare** with the four recorded methods, including errors by direction:
  no reference change is a withdrawal, so every predicted withdrawal is wrong.

The held-out pairs were read once, after the method, data, analysis and success
criteria were frozen. The benchmark has been public since, so the held-out split
is a clean test only for work that keeps it out of development. The
benchmark's own README calls the success criteria a "preregistered gate"; they
were fixed and hash-bound before the held-out read but not filed with an
external registry.

## How it was built

`construction/theft_causal_benchmark.py` builds each case from one of four story
paragraphs and the nine condition sentences, with no model calls. The
references come from `reference-contract/theft.json`, which records the
decisions, conditions, facts, evidence and documents of the theft process that
the sources support, with verbatim quotations;
`construction/theft_branch_diagnostic.py` derives from it which documents each
condition governs. Both scripts are kept as they ran, with their original
paths (`reference_contracts/theft.json` is `reference-contract/theft.json`
here), and they built the first version of the benchmark, before the two
amendments. Two amendments, both
made before the held-out pairs were read, turned "receipt and valuation" into
"receipt or valuation" and added the bicycle purchase voucher. The files in
`representation/` are what CasePath's agents extracted from the sources with a
language model; they are model output, not reference labels.

## What it does not cover

The references were derived from an agent-built contract and were not reviewed
by a legal expert. Every case switches on at most one condition, so interactions
between conditions are not tested, and no reference change is a withdrawal, so a
correct withdrawal cannot be measured. Only one requirement has alternative
routes. The held-out stories vary the claim setting, not the conditions. In
`BENCHMARK_V3.json`, two convenience fields are stale: `gold_branch_documents`
lists one document instead of two for the four bicycle cases, and
`branch_document_universe` lists 11 of the 12 documents; the scorer uses only
`acceptable_signed_deltas`. Eight passages carry a wrong source label, corrected
in `SOURCES.md`.

## Licence

The case texts, references, catalogue, representation, documentation and
attribution files are released under CC BY 4.0 (`LICENSE-DATA`); the code under
Apache 2.0 (`LICENSE-CODE`). The quoted passages from the policy terms, the
claim form and the model conditions remain the property of their issuers and are
excluded from the CC BY 4.0 grant; the federal-law passages are official
enactments. See `SOURCES.md`.
