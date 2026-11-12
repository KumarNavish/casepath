# Task: derive document states from the rule text (theft)

You are one of two evaluators working independently. Decide, for a set of designed theft files, the state of
every document the rules name, using only the rule text in `rule_text.md`, the catalogue in `catalogue.json` and
the designed facts in `designs.json`.

## What you may read

Only the five files in this folder: `TASK.md` (this file), `SCHEMA.md`, `rule_text.md`, `catalogue.json` and
`designs.json`. Do not read anything else in the surrounding folders or repository, do not look for an existing
program or answer for these files, and do not consult the other evaluator. Follow the rule text; do not try to
reproduce what some existing system would answer. Do not call any language model or other paid service.

## What you are given

- `rule_text.md`: the rules, including the convention of this benchmark for facts a file does not mention.
- `catalogue.json`: per type, its facts (id and question, as in the rule text) and its documents (id, title as in
  the rule text, and what a sufficient copy must show).
- `designs.json`: 60 files. For each: its id, its type, the state of every fact of its type, as one of
  `stated_true` (the file states that the fact holds), `denied` (the file states that it does not hold),
  `not_mentioned` (the file says nothing about it), `raised_and_left_open` (the file raises it and leaves it
  unsettled); and the documents supplied with the file, each marked `sufficient` or `insufficient` (insufficient:
  it lacks one item it must show). Take these as given.

## What you decide

For every file and every document of its type, exactly one of:

| State | Meaning |
|---|---|
| `request` | The document must be requested now. |
| `hold` | Whether it is needed depends on a fact the file leaves unresolved; it waits for the answer. Name the fact(s). |
| `not_needed` | The document is not needed for this file. |
| `present_sufficient` | Supplied, needed, and the copy is sufficient. |
| `present_insufficient` | Supplied, needed, but insufficient, so it must be requested again. |

If a supplied document is not needed or held under your reading, or a document the rule text calls optional (not
mandatory) is or is not supplied, decide what the rule text says and record it in `SEMANTICS.md`.

## What you deliver (in your own working folder, not here)

1. `evaluate.py`: deterministic Python 3, standard library only, reading `catalogue.json` and `designs.json`
   (paths as arguments) and writing `reference.json` in the format of `SCHEMA.md`. It must encode the rule text,
   not a hand-typed table of answers per file. Two runs give byte-identical output.
2. `reference.json`: its output on this folder's files.
3. `SEMANTICS.md` (short): how you treated, quoting the deciding words of the rule text: a fact not mentioned; a
   fact raised and left open; a denied defining event; an open defining event; documents on a step reached under
   every answer and under some answers; optional and conditional documents; supplied documents (sufficient,
   insufficient, and ones otherwise not needed or held); stops. Where the text does not decide, make a choice and
   list it under a final heading `Ambiguities` (the question, the options, your choice and why).
