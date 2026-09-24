# The provenance-chain inheritance zero is a locator-equality artifact

**Diagnosis only. No rescoring, no new inference, no evidence file changed.**

`provenance_chain_inheritance_rate` reads exactly `0.000` for all three arms of the assessed-state
analysis, including the compiled equivalent, which is identical to CasePath on every other metric.
The manuscript previously reported this as a measured property. It is not one.

## What the metric actually tests

`vendor_native_evaluator/scorers/grounding.py` builds, for each active evidence contract and each
(decision, fact, capability, document) endpoint, the intersection of the four reference concepts'
`source_requirements`, and counts a hit only when

```python
inherited.issubset(set(item.provenance))
```

holds for every endpoint. Both sides are `SourceLocator` values, and `contracts/schema.py` defines
that as a strict model with twelve fields: `artifact_id`, `artifact_sha256`, `locator_kind`, `page`,
`exact_text`, `text_start`, `text_end`, `image_region`, `source_version`, `effective_date`,
`json_pointer`, `canonical_value_sha256`. Set membership therefore requires **exact structural
identity across all twelve**, including text offsets and canonical hashes.

## What the producer emits

Provenance is present, not missing. Scanning 120 completed CasePath cells finds **3,104** locator
objects, every one populating the same six fields and leaving the rest null:

```json
{"artifact_id": "policy-defect_mold_heating-v1.structured",
 "artifact_sha256": "30f463ae…", "canonical_value_sha256": "a4bbe3ef…",
 "json_pointer": "/process_catalog/transitions/0/assertion",
 "locator_kind": "json_pointer", "source_version": "casepath.static-rule-templates/3.0.0",
 "page": null, "exact_text": null, "text_start": null, "text_end": null,
 "image_region": null, "effective_date": null}
```

## Why the zero is uninformative

Expectations are non-zero: 738 across the observed CasePath rows, with 0 hits. A behavioural zero
that lands *exactly* on zero across 738 independent opportunities, identically in three arms, is far
better explained by a comparison that can never succeed than by a controller that never inherits.
The producer expresses provenance as a `json_pointer` locator into the `.structured` policy
artifact; the equality test demands a reference locator agreeing on all twelve fields.

## Bounded claim

**Supported.** The metric compares full structural locator identity. The producer does emit
provenance locators, of `locator_kind: json_pointer`, with text-span fields null. Expectations are
738 and hits are 0 in all three arms. The zero therefore does not measure whether chains inherit
source support.

**Not supported.** That provenance inheritance in fact succeeds. I did not read the reference side's
`source_requirements` values, so which field diverges — `locator_kind`, `artifact_id`, or the null
text fields — is unverified. Nothing here licenses claiming exact-source entailment, which the
paper correctly disclaims on independent grounds.

**Not attempted.** Rescoring. Establishing the true inheritance rate needs a locator comparison at
matching granularity, which is a change to the frozen evaluator and belongs to a separate approved
analysis, not to this note.
