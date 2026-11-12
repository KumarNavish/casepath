# File formats (UTF-8 JSON)

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
