# Rule schema for the review

`rules.json` holds evidence rules extracted from Swiss household-insurance law, policy terms and a claim form. Each
rule says which documents a claims handler should request, and under which condition. Review each rule against the
passages it cites (`passages.json`) and edit it so that it says what the passages say. Save the result as a file with
the same structure (for example `rules_reviewed.json`) and check it with `python3 validate.py rules_reviewed.json`.

## File

```json
{"pack": "<free text>", "rules": [<rule>, ...]}
```

## Rule

| Field | Meaning | May change? |
|---|---|---|
| `rule_id` | Identifier, e.g. `overlay_rule_001`. | No. Every original rule must stay in the file. |
| `title` | What the rule requires, in words. | Yes (free text). |
| `process_node`, `requirement_kind` | Where the rule sits in the claims process; its kind. | Keep as is. |
| `condition` | `null` if the rule always applies, else `{"guard_id", "text", "cited"}`. | Yes: text, citations; it may be added (set `guard_id` to `null`) or removed (set `condition` to `null`). |
| `facts` | What must be established, each with its `evidence`. | Yes, see below. |
| `confirming_evidence` | Documents that confirm the condition once it holds, or `null`. Same shape as one evidence item. | Yes: routes and citations. |

### Condition and how it is judged

`condition.text` is a statement about a claim. For every claim, a model judges each condition of the pack as true,
false or unresolved, quoting the claim; code then applies the rules. Every condition in the file is judged.

- Unchanged condition: keep `guard_id` and `text` as they are.
- Changed wording: edit `text` and keep the `guard_id`. The loader sees that the text differs from the original and
  creates a new condition (`<guard_id>.rev-<hash>`), which is judged as a new statement. The old wording is no
  longer used.
- New condition on a rule that had none: `{"guard_id": null, "text": "...", "cited": [...]}`.
- Write one checkable statement about the claim, as narrow or broad as the passages make the requirement. Where
  the passages make the requirement depend on two things, state both in the one condition ("A and B"), or split
  the rule (below).

### Facts, evidence and routes

```json
{"fact_id": "overlay_rule_001.f01", "statement": "...", "cited": [...],
 "evidence": [{"capability_id": "overlay_rule_001.f01.c01", "must_show": "...", "cited": [...],
               "routes": [{"route_id": "r1", "documents": ["<catalogue name>", ...], "why": "..."}]}]}
```

- `routes` are **alternatives**: any one route satisfies the evidence item.
- The `documents` of one route are **joint**: all of them are needed together.
- To accept either of two documents, use two routes with one document each. To require both, put them in one route.
- Document names must be copied exactly from `catalogue.json` (`name`). Documents cannot be invented.
- A route needs at least one document. An evidence item may have no route (`"routes": []`): then no catalogue
  document can show it and nothing is requested for it. A fact needs at least one evidence item.
- Keep existing `fact_id`, `capability_id` and `route_id`. New ones: `<rule_id>.fNN` for a fact,
  `<fact_id>.cNN` for an evidence item, `rN` for a route (unique within its evidence item).
- `why` and `must_show` are explanations; edit them freely.

### Splitting a rule

If only part of a rule depends on a condition, move that part to a new rule whose id is the original id plus a
suffix, e.g. `overlay_rule_010.a`, with its own `condition`. The original rule must keep at least one fact.

### Citations

`cited` lists passage references. `theft-source-0042#p2` means a statement taken from passage `theft-source-0042`
(the part after `#` numbers the statement within the passage). When you add a citation you may give the bare passage
id (`theft-source-0042`). Every passage part must exist in `passages.json`. Do not cite anything else.

## Toy example (not one of the rules)

Passage `toy-0001`: "If the insured animal is injured in an accident, the policyholder must submit the veterinarian's
invoice or, where no treatment took place, a veterinarian's written assessment."

Extracted (wrong: the two documents are joint, and the condition is broader than the passage):

```json
{"rule_id": "toy_rule_001", "title": "Document the animal injury",
 "condition": {"guard_id": "toy_guard_001", "text": "An insured animal is involved in the claim.", "cited": ["toy-0001#p1"]},
 "facts": [{"fact_id": "toy_rule_001.f01", "statement": "The injury and its treatment are documented.", "cited": ["toy-0001#p1"],
   "evidence": [{"capability_id": "toy_rule_001.f01.c01", "must_show": "Injury and treatment", "cited": ["toy-0001#p1"],
     "routes": [{"route_id": "r1", "documents": ["Veterinarian's invoice", "Veterinarian's written assessment"], "why": ""}]}]}],
 "confirming_evidence": null}
```

Reviewed (condition narrowed; documents made alternatives):

```json
{"rule_id": "toy_rule_001", "title": "Document the animal injury",
 "condition": {"guard_id": "toy_guard_001", "text": "An insured animal was injured in an accident.", "cited": ["toy-0001#p1"]},
 "facts": [{"fact_id": "toy_rule_001.f01", "statement": "The injury and its treatment are documented.", "cited": ["toy-0001#p1"],
   "evidence": [{"capability_id": "toy_rule_001.f01.c01", "must_show": "Injury and treatment", "cited": ["toy-0001#p1"],
     "routes": [{"route_id": "r1", "documents": ["Veterinarian's invoice"], "why": ""},
                {"route_id": "r2", "documents": ["Veterinarian's written assessment"], "why": "where no treatment took place"}]}]}],
 "confirming_evidence": null}
```
