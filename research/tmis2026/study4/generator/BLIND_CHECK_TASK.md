# Blind-check session: fixed instruction

You read synthetic claim files and say, for each question, what the file states, and for each attachment whether
it shows everything it must. You do not know how the files were designed, and you must not try to find out.

## What you may read

- this instruction;
- the blind-check inputs you are given (`blindcheck/in/round<k>/<file_id>.json`).

Nothing else: no other file of the repository (in particular no design, bundle, key, reference or other
session's output), no rule text, no program. Do not call any other model or service. Judge each file on its own.

## Input, per file

```
{"file_id": "...",
 "text": "<the claimant's message>",
 "attachments": [{"label": "A1", "document_title": "...", "must_show": ["...", ...], "text": "..."}],
 "questions": [{"label": "Q1", "question": "..."}]}
```

## What you decide

For every question, from the message and its attachments together, exactly one state:

| State | When |
|---|---|
| `stated_true` | The file says, plainly or so that it follows unmistakably, that the answer is yes. |
| `stated_false` | The file says, plainly or so that it follows unmistakably, that the answer is no. |
| `open` | The file raises the matter but leaves it unsettled: the claimant does not know, has not decided, or the parties disagree and nothing in the file settles it. |
| `not_mentioned` | The file says nothing from which the question could be answered, and does not raise it. |

Take the question's words literally: a circumstance that is close to the question but not what it asks is not a
yes. A yes or no said with some hesitation but with a concrete basis is stated, not open. Do not infer an answer
from what usually happens; silence is `not_mentioned`, never `stated_false`.

For every attachment: `sufficient` if it shows every item of its `must_show` list (an item worded as applying
only in some cases, such as "any ... clause", "where ...", "if any", counts only if it applies to this file);
otherwise `insufficient`, naming each missing item by copying its text exactly from `must_show`.

Quote, for every state other than `not_mentioned`, the shortest passage (at most 30 words, verbatim, from the
message or an attachment) on which you rely.

## Output, per file

One UTF-8 JSON file, `blindcheck/out/round<k>/<file_id>.json`:

```
{"file_id": "<file_id>",
 "facts": {"Q1": {"state": "stated_true" | "stated_false" | "open" | "not_mentioned", "quote": "<verbatim or empty>"}},
 "attachments": {"A1": {"state": "sufficient"} | {"state": "insufficient", "missing": ["<item copied from must_show>"]}}}
```

Every question label and every attachment label of the input appears exactly once.
