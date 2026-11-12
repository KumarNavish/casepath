# Task: derive document states from the rule text

You are one of two evaluators working independently. Your job is to decide, for a set of synthetic tenancy claims,
which documents the rules require, using only the rule text in `rules.json` and the claim facts in `claims.json`.

## What you may read

Only the four files in this folder: `TASK.md` (this file), `SCHEMA.md`, `rules.json` and `claims.json`. Do not read
anything else in the surrounding folders or repository, do not look for any existing program or answer for these
claims, and do not consult the other evaluator. Do not try to reproduce what some existing system would answer:
follow the rule text. Do not call any language model or other paid service.

## What you are given

- `rules.json`: for each of three dispute types (`defect_mold_heating`, `lease_termination_dispute`,
  `rent_increase_dispute`): a title; the rule prose (`content`), which ends with a silence-policy clause; a
  condition catalogue (the names of the facts of that dispute type); and a process catalogue: the steps (`nodes`),
  the transitions between steps with their conditions, and the documents, each with its requirement class
  (`mandatory`, `conditional` or `optional`), its condition (if any) and the step(s) it belongs to.
- `claims.json`: 96 claims. For each claim: its id, its dispute type, the state of every fact of its dispute type,
  and the documents the tenant has already supplied. There is no claim text: the facts are given to you already
  decided, as one of
  - `stated_true`: the claim states that the fact holds;
  - `denied`: the claim states that the fact does not hold;
  - `not_mentioned`: the claim says nothing about the fact;
  - `raised_and_left_open`: the claim raises the fact but leaves it open (the tenant does not know or has not
    decided).
  Every supplied document is marked `sufficient` or `insufficient` (insufficient: it lacks content the document
  should contain). Take these markings as given; you do not judge document contents.

Which fact name corresponds to which condition or phrase in the rule text is part of what you establish from the
text; say how you matched them in `SEMANTICS.md`.

## What you decide

For every claim and for every document of the claim's dispute type (every entry of that dispute type's
`process_catalog.documents`), exactly one of:

| State | Meaning |
|---|---|
| `required_now` | The document must be requested from the tenant now. |
| `held` | Whether the document is needed depends on a fact the claim leaves open; it is not requested now but waits for the answer to a question. |
| `not_needed` | The document is not needed for this claim. |
| `supplied_sufficient` | The tenant supplied it, it is needed, and the supplied copy is sufficient. |
| `supplied_insufficient` | The tenant supplied it, it is needed, but the supplied copy is insufficient, so it must be requested again (it counts as to be requested). |

If a supplied document turns out to be not needed or held under your reading of the rules, decide what you think
the rule text says and record the choice in `SEMANTICS.md`.

## What you deliver

In your own working folder (not in this folder):

1. `evaluate.py`: a deterministic Python 3 program, standard library only, that reads `rules.json` and
   `claims.json` (paths as command-line arguments) and writes `reference.json` in the format of `SCHEMA.md`. It
   must use the rule catalogue in `rules.json` rather than a hand-typed table of answers per claim. Running it twice
   must give byte-identical output.
2. `reference.json`: the output of `evaluate.py` on the two files of this folder.
3. `SEMANTICS.md` (short): how you treated each of the cases below, each with the words of the rule text that
   decide it (quote them):
   1. a fact the claim does not mention;
   2. a fact raised and left open;
   3. a defining event of a dispute (if you find one in the text) that the claim denies;
   4. a defining event left open;
   5. documents on a step that is reached whatever the answer to an open question, and documents on a step that is
      reached only under some answers;
   6. optional documents and conditional documents;
   7. a supplied document (sufficient and insufficient), including one that would otherwise be not needed or held;
   8. how you matched fact names to the conditions in the rule text (transition conditions and document
      conditions).

   Where the rule text does not decide a question, make a choice, say plainly that it is your choice, and list it
   under a final heading `Ambiguities` (one entry per choice: the question, the options, what you chose and why).

Work from the text. If you notice that the text seems to contradict itself or leaves a case open, that is a
finding: record it under `Ambiguities` rather than resolving it silently.
