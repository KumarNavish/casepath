# Held-out theft statistical protocol v4 — route-aware final form

Goal contract SHA-256: `a9cd441ef939e36d7ed2c546b76aa41554813aba11ba1a379f23479ded4cc37b`.

Version 4 supersedes the flat-gold scoring portion of v3. It preserves v3's split, weighting, inference, chain-attribution, and positive-claim gates, while correcting one pre-hidden benchmark defect: the source contract defines a purchase receipt and an expert valuation as alternative routes for one scheduled-valuables requirement. Predicting either route is sufficient; predicting both incurs an extra-document penalty.

## Frozen inputs

- route-aware benchmark: `theft_causal/BENCHMARK_V2.json`, SHA-256 `7e04d2d6d549cccc1e037f69d37c7faa5e155e9cef1eff70c4e8fca1598a22b6`;
- shortcut preflight: `theft_causal/SHORTCUT_PREFLIGHT_V2.json`, SHA-256 `4351e6309bbcb196a1abe493d790c3ad68ba949fae6f629add55bd77fe89131f`;
- source snapshot v2: SHA-256 `9d34231a655d16ef55348bc3018e90a3276ed8022859d8b3064177b0b4afb2d1`;
- extracted propositions: SHA-256 `bd89ac3100dc1ba44a901efedf18092d0a1566f55100e3bf48f9226270b4c553`;
- macro process graph: SHA-256 `d7e83160dfbdb6b195adb634d021a50ff1131b5e760a02b8f8c2180a0729173d`;
- proposition-complete final refinement: SHA-256 `c0010b155b6cb0b90ee660b4d07553c522c5522cda4324f599107c146b623571`;
- full closed catalogue: SHA-256 `7dbd0c23d6452f85b47854d39122bdf44fc1ae196e152888ee24828e21344572`;
- route-aware analyzer: `theft_confirmatory_analysis_v4.py`, SHA-256 `f81f499f981910505e6d385c980e7999ceafbcd799bb1839d051943c1eb71ddd`.
## Split and stopping boundary

Only context index 0 from each of the nine branch families is development: nine pairs / eighteen units. Context indices 1–3 are hidden: twenty-seven pairs / fifty-four units. No hidden unit has been opened. Development may determine whether the final method is admitted to the hidden read; it may not estimate the paper's confirmatory effect.

The remaining hidden units are opened once only after a final manifest binds source extraction, graph synthesis, refinement, document mapping, guard interpretation, product service, four arm runners, route-aware evaluator, model, provider, decoding, and every prompt hash. A failed development gate closes the positive theft experiment without reading hidden outcomes.

## Arms and matched execution

The four conditions are B1 direct, B3 complete process/evidence representation as context, B6 evidence-first composition, and B5 process-compiled. All use `openai/gpt-5.6-terra`, OpenAI-only provider routing, temperature 0, the same source snapshot, case packet, 33-document catalogue, and closed output vocabulary.

One-time B5 source extraction, process synthesis, proposition-complete refinement, and capability-to-document mapping are charged and reported. Per-case B5 inference evaluates one source guard independently across the complete roster, with exact-quote admission per unit. B3 receives the same frozen macro graph and evidence overlay but predicts the checklist itself. B1 and B6 receive no hidden gold structure.

## Route-aware target

For pair `i`, the frozen benchmark supplies one or more acceptable signed document-delta realizations. Each realization selects exactly one document route per evidence requirement. The evaluator selects the acceptable realization that maximizes symmetric F1 against the arm's prediction; ties are resolved deterministically by true positives, precision, recall, smaller gold size, and lexical order.

This is not leniency toward over-requesting. If either a receipt or valuation is sufficient, predicting one can score 1.0 and predicting both scores 2/3. Documents outside the selected valid realization are spurious. All other branch families have one acceptable realization.
## Endpoints and weighting

Primary: pooled route-aware signed-delta micro-F1 over the frozen finite corpus. `+document` and `-document` are distinct atoms.

Secondary: route-aware precision, recall, exact-realization rate, never-changed rate, spurious atoms, missed atoms, and equal-branch-family mean pair F1. The headline corpus score pools atoms. Robustness inference treats each of the nine branch families equally, retaining every context inside a selected family.

B5 mechanism endpoints are the fraction of predicted delta atoms attributable to a source-grounded rule whose applicability guard changed, the fraction of the selected gold realization with such a chain, resolver-versus-active request counts, evidence gaps, and availability of a justified next action. Every B5 request must expose process-node anchor, guard, fact, evidence capability, proposition ids, exact source spans, and document route.

## Uncertainty and randomization

Use 10,000 branch-family cluster-bootstrap draws with seed `20260917`. Report percentile 95% intervals for every arm and B5-minus-comparator micro-F1.

For B5 versus each comparator, enumerate all `2^9 = 512` family-level arm swaps. The statistic is the equal-family mean context-level route-aware F1 difference. Report one-sided exact p-values and Holm adjustment across the three comparisons.

For pairing specificity, retain B5 predictions and permute complete acceptable target families across different branches while preserving context position. Report all eight nonidentity cyclic shifts plus 5,000 seeded derangements, the 95% null range, and the plus-one p-value. A prediction is evaluated against the best acceptable realization of its permuted target.

## Development admission gate

B5 is admitted to the hidden read only if, on the nine development pairs, it exceeds the strongest matched comparator by at least 0.10 micro-F1, has route-aware precision at least 0.70, keeps its predicted-to-selected-gold atom ratio in `[0.75, 1.50]`, attributes at least 90% of its predicted changes to changed source guards, covers at least 80% of selected gold atoms with such chains, and has no orphan insertion path. This gate is a resource and mechanism screen, not confirmatory evidence.
## Hidden positive-claim gate

The positive theft method claim survives only if all conditions hold on the twenty-seven hidden pairs:

1. B5 micro-F1 exceeds B1, B3, and B6 by at least 0.10 absolute each.
2. All three Holm-adjusted family-swap p-values are at most 0.05.
3. B5 precision is at least 0.70 and the predicted-to-selected-gold atom ratio is within `[0.75, 1.50]`.
4. At least 90% of predicted delta atoms are chain-attributed and at least 80% of selected gold atoms have a changed-guard chain.
5. Correct pairing exceeds the 97.5th percentile of the cross-family wrong-pairing null.
6. Every requested document is admitted through a complete source-grounded process/evidence chain; no direct orphan insertion exists.

If B3 or B6 matches B5, explicit compilation is not established as necessary. If B5 improves only by changing more documents, the claim is unsupported. No prompt, source, route, catalogue, ontology, threshold, parser, or scorer changes after the hidden read.

## Missingness and release

Provider, parse, exact-quote, roster, or manifest failures remain failures of execution, not negative predictions. Unknown completion is reconciled from receipts before any bounded retry. The confirmatory analysis requires a complete frozen roster.

All development and hidden outputs, selected alternative realizations, failures, receipts, costs, hashes, bootstrap draws, randomization results, and superseded v1 benchmark artifacts are included in the anonymous release. Version 4 changes no case text and no hidden outcome; it repairs target semantics before any hidden unit is opened.

## Version-5 development amendment — before any hidden read

Version 5 keeps every numerical gate, family weighting, randomization test, bootstrap seed, model/provider setting, case text, split, and closed document catalogue from Version 4. Two source-derived corrections are bound before B5 development and before any hidden unit is opened:

1. `BENCHMARK_V3.json` restores the bicycle purchase voucher omitted by v2. The independent reference contract already states that `PR_bicycle_claimed` opens both the purchase voucher and the photographed detailed estimate; these are distinct, non-alternative source-named requirements. The scheduled-valuables receipt/valuation remains an OR route.
2. `casepath.evidence-overlay/3.0.0` separates unresolved process state from evidence obligations. An unresolved guard becomes a justified state-resolution next action and contributes no branch-specific checklist document. A true but not documentary-confirmed guard may contribute a mapped applicability-confirmation route. Active obligation evidence continues to come only from compiled source facts/capabilities.

The source snapshot, 308-proposition refinement, v9 document map, case interpreter, benchmark cases, development roster, matched comparator raw predictions, and all admission thresholds are otherwise unchanged. `TARGET_ROUTE_AUDIT_V5.json` is source-only and requires every frozen gold requirement to have at least one route through an active requirement or applicability-confirmation capability; it consumed zero case units. Hidden theft remains 27 pairs / 54 units and is unopened at this amendment.
