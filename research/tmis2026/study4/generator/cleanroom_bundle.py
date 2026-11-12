"""Export, per regime, exactly what a blind evaluator may see (SPEC.md step 2b; modelled on cleanroom/bundle/).

Run:  python3 -I -B study4/generator/cleanroom_bundle.py --regime tenancy
Writes study4/dev/<regime>/cleanroom_bundle/{TASK.md, SCHEMA.md, rule_text.md, catalogue.json, designs.json,
BUNDLE_MANIFEST.json}.

Contained: the regime's rule_text.md (byte for byte); the document catalogue (per type: type id and title, its
facts with their question, its documents with id, title and must_show); per design: file id, type, the state of
every fact and the supplied attachments with their designed sufficiency.
Not contained: references of any kind, the workflow, rules.json (steps, conditions, passages), product code, the
level, the story, the language, the noise flag, the missing item's name, the true value of an open fact,
constraint adjustments.
"""
import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import genlib as G  # noqa: E402

STATE_NAMES = {"stated_true": "stated_true", "stated_false": "denied", "open": "raised_and_left_open",
               "not_mentioned": "not_mentioned"}

TASK = """# Task: derive document states from the rule text ({regime})

You are one of two evaluators working independently. Decide, for a set of designed {regime} files, the state of
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
- `designs.json`: {n} files. For each: its id, its type, the state of every fact of its type, as one of
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
"""

SCHEMA = """# File formats (UTF-8 JSON)

## `catalogue.json`

```
{"regime": string, "types": [{"type": string, "title": string,
   "facts": [{"fact": string, "question": string}],
   "documents": [{"document": string, "title": string, "must_show": [string]}]}]}
```

## `designs.json`

```
{"files": [{"file_id": string, "type": string,
   "facts": {<fact>: "stated_true" | "denied" | "not_mentioned" | "raised_and_left_open"},
   "attachments": [{"document": string, "as_designed": "sufficient" | "insufficient"}]}]}
```

## `reference.json` (your output)

An object keyed by file id; for each file, an object keyed by every document of its type:

```
{<file_id>: {<document>: {"state": "request" | "hold" | "not_needed" | "present_sufficient" |
                                   "present_insufficient",
                          "waits_for": [<fact>, ...]   // only with "hold"
                         }}}
```

Write it with `json.dump(obj, f, indent=2, sort_keys=True)` followed by a newline.
"""


def build(regime_name, rules_dir=None, out=None):
    regime = G.Regime(regime_name, rules_dir)
    out = Path(out) if out else G.DEV / regime_name
    designs = [G.read_json(p) for p in sorted((out / "designs").glob("*.json")) if p.name != "MANIFEST.json"]
    b = out / "cleanroom_bundle"
    if b.exists():
        shutil.rmtree(b)
    b.mkdir(parents=True)
    shutil.copyfile(regime.dir / "rule_text.md", b / "rule_text.md")
    cat = {"regime": regime_name, "types": [
        {"type": t["id"], "title": t["title"],
         "facts": [{"fact": f["id"], "question": f["question"]} for f in t["facts"]],
         "documents": [{"document": d["id"], "title": d["title"], "must_show": d["must_show"]}
                       for d in t["documents"]]} for t in regime.rules["types"]]}
    G.write_json(b / "catalogue.json", cat)
    files = []
    for d in sorted(designs, key=lambda x: x["file_id"]):
        files.append({"file_id": d["file_id"], "type": d["type"],
                      "facts": {f: STATE_NAMES[s] for f, s in d["facts"].items()},
                      "attachments": [{"document": a["document"],
                                       "as_designed": "sufficient" if a["sufficient"] else "insufficient"}
                                      for a in d["attachments"] if a["supplied"]]})
    G.write_json(b / "designs.json", {"files": files})
    (b / "TASK.md").write_text(TASK.format(regime=regime_name, n=len(files)), encoding="utf-8")
    (b / "SCHEMA.md").write_text(SCHEMA, encoding="utf-8")
    names = ["TASK.md", "SCHEMA.md", "rule_text.md", "catalogue.json", "designs.json"]
    G.write_json(b / "BUNDLE_MANIFEST.json", {"regime": regime_name, "files": {n: G.sha256_file(b / n) for n in names},
                                              "built_by": "study4/generator/cleanroom_bundle.py",
                                              "builder_sha256": G.sha256_file(Path(__file__))})
    return b


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--regime", required=True)
    ap.add_argument("--rules-dir")
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    b = build(a.regime, a.rules_dir, a.out)
    print(f"clean-room bundle written to {b}")


if __name__ == "__main__":
    main()
