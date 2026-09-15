# Where the process graph comes from today

Work-order step 2. The answer decides the scope of everything after it.

## The finding

**The process graph is hand-authored and handed to the model. It is not induced from the authoritative
sources.** The two artifacts are entirely disconnected.

`casepath_api/corpora/synthetic-150/policy/swiss-authority-passages-v3.json` holds **19 real Swiss law
passages** — OR Art. 257d, 257g, 259a, 259g and others — with exact German text, Fedlex snapshot ids and
source URLs. Genuine authoritative material.

`casepath_api/corpora/synthetic-150/policy/static-rule-templates-v3.json` holds **three hand-authored
process templates**, one per domain, each containing:

| | per template |
|---|---|
| process nodes | 11, with id, label, responsibility, terminal flag |
| transitions | 14, with source, target and branch condition |
| document requirements | 11, each with `required_at_node_ids` and a requirement class |

Its own metadata states `model_visibility: all_three_templates_identical_for_every_case`, so every case
sees every template, and `contains_selected_paths: false`, so activation is genuinely the model's work.

**Zero of the nineteen authority passages are referenced anywhere in the templates.** No node, transition
or document requirement cites an `authority_id`, a `snapshot_id` or an article. The law is present as
context; it grounds nothing structural.

## What that means for the claimed chain

```
AUTHORITATIVE SOURCE → PROCESS NODE → OBLIGATION → FACT → EVIDENCE CAPABILITY → DOCUMENT
```

Of those six links, the product implements the last two as a lookup and the middle one not at all:

| link | status today |
|---|---|
| source → process node | **absent**: the graph is authored by hand, citing no source |
| process node → active obligation | present: the model activates branch conditions per case |
| obligation → required fact | **absent**: there is no fact layer |
| fact → evidence capability | **absent**: there is no capability layer |
| evidence capability → document | **lookup**: `required_at_node_ids` maps node to document type directly |
| document → sufficiency | present and tested: the evidence-state layer |

So the system performs **case-specific activation of a given graph**, which is a real capability, but not
**process induction from authoritative sources**, which is the paper's thesis.

## The same shortcut exists on the evaluation side

`arena_v1/generator.py` hardcodes `PACKS[domain]["requirements"]` — the requirement-to-document-set map
per domain. The benchmark therefore cannot test process identification either: the gold checklist is a
constant of the domain, not a consequence of a graph.

## Scope this implies

Reusable as-is: the 150-claim corpus with 207 real sources, the 19 Fedlex passages, the case interpreter
and its activation machinery, the evidence-state layer, the request planner, the acceptance-contract
evaluator scaffolding, the product shell with its gate rendering, and the release and reproduction
machinery.

To be built: the authority proposition extractor, the process synthesiser, the process critic, a real
obligation compiler with explicit fact and evidence-capability layers, process-identification metrics, a
benchmark whose gold graph varies with the source corpus rather than with a domain label, and the B1–B6
baselines for that task.

The shortcut file is the thing the work order says to eliminate, and it currently supplies the entire
answer.
