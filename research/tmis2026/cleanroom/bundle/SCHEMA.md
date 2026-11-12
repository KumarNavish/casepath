# File formats

All files are UTF-8 JSON.

## `rules.json` (input)

```
{
  "dispute_types": [
    {
      "dispute_type": string,              // e.g. "rent_increase_dispute"
      "template_id": string,
      "title": string,
      "content": string,                   // the rule prose, ending with the silence-policy clause
      "condition_catalog": [string, ...],  // the fact names of this dispute type, as used in claims.json
      "process_catalog": {
        "nodes": [                         // the process steps
          {"node_id": string, "label": string, "responsibility": string, "terminal": bool}
        ],
        "transitions": [
          {"edge_id": string, "source_node_id": string, "target_node_id": string,
           "condition": string, "optional_path": bool}
        ],
        "documents": [
          {"document_type": string, "label": string,
           "requirement_class": "mandatory" | "conditional" | "optional",
           "condition": string | null,
           "required_at_node_ids": [string, ...]}
        ]
      }
    }
  ]
}
```

A `document_type` is unique within a dispute type; the same `document_type` may occur in more than one dispute
type.

## `claims.json` (input)

```
{
  "claims": [
    {
      "claim_id": string,
      "dispute_type": string,              // one of the dispute types of rules.json
      "facts": {                           // one entry for every name in that dispute type's condition_catalog
        <fact name>: "stated_true" | "denied" | "not_mentioned" | "raised_and_left_open"
      },
      "attachments": [                     // documents already supplied by the tenant; may be empty
        {"document_type": string,          // a document_type of that dispute type
         "as_designed": "sufficient" | "insufficient"}
      ]
    }
  ]
}
```

## `reference.json` (your output)

An object keyed by claim id; for each claim, an object keyed by every `document_type` of its dispute type, with
one of the five states. Every claim of `claims.json` and every document of its dispute type must appear; nothing
else.

```
{
  <claim_id>: {
    <document_type>: "required_now" | "held" | "not_needed" | "supplied_sufficient" | "supplied_insufficient"
  }
}
```

Write it with `json.dump(obj, f, indent=2, sort_keys=True)` followed by a newline.

## A tiny made-up example

This example uses an invented dispute type that is not in `rules.json`; it only shows the formats. Its output
covers only a stated fact and a sufficient supplied document.

`rules.json` (excerpt):

```json
{
  "dispute_types": [
    {
      "dispute_type": "example_parking_dispute",
      "template_id": "example-v1",
      "title": "Example parking-space dispute",
      "content": "Check the parking contract. Request the damage photos only when that branch is active.",
      "condition_catalog": ["car_damaged"],
      "process_catalog": {
        "nodes": [
          {"node_id": "ex_start", "label": "Check contract", "responsibility": "claim_handler", "terminal": false},
          {"node_id": "ex_damage", "label": "Assess damage", "responsibility": "claim_handler", "terminal": false},
          {"node_id": "ex_close", "label": "Close", "responsibility": "claim_handler", "terminal": true}
        ],
        "transitions": [
          {"edge_id": "ex_e1", "source_node_id": "ex_start", "target_node_id": "ex_damage",
           "condition": "car damaged", "optional_path": true},
          {"edge_id": "ex_e2", "source_node_id": "ex_damage", "target_node_id": "ex_close",
           "condition": "damage assessed", "optional_path": false}
        ],
        "documents": [
          {"document_type": "parking_contract", "label": "Parking contract", "requirement_class": "mandatory",
           "condition": null, "required_at_node_ids": ["ex_start"]},
          {"document_type": "damage_photos", "label": "Damage photos", "requirement_class": "conditional",
           "condition": "scenario flag 'car_damaged' is active", "required_at_node_ids": ["ex_damage"]}
        ]
      }
    }
  ]
}
```

`claims.json`:

```json
{
  "claims": [
    {
      "claim_id": "example_claim_001",
      "dispute_type": "example_parking_dispute",
      "facts": {"car_damaged": "stated_true"},
      "attachments": [{"document_type": "parking_contract", "as_designed": "sufficient"}]
    }
  ]
}
```

`reference.json`:

```json
{
  "example_claim_001": {
    "damage_photos": "required_now",
    "parking_contract": "supplied_sufficient"
  }
}
```
