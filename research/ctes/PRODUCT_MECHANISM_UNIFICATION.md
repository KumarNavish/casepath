# Two product surfaces, two propositions, one mechanism each

The open question was whether CasePath's six-role workflow already implements the scientific primitive,
making the added gate redundant, and whether the product now carries two overlapping epistemic safety
systems. It carries two mechanisms because there are two distinct propositions, and this records which is
which so that neither is duplicated.

## What the six-role workflow already guarantees, by type

In `agent_work/contracts.py`, `SourceSpan.scope` is declared

```python
scope: Literal["source_statement_not_established_fact"] = "source_statement_not_established_fact"
```

a `Literal` with exactly one admissible value. No caller — deterministic worker or external model — can
construct a span that asserts an established fact. The proposition *"this quotation is a source statement,
not an established fact"* is therefore guaranteed by construction on that path, not by a check. This is a
genuinely strong property and it predates this work.

It is also why the preserved real external-model run is a no-op for the added gate: the Facts specialist
emitted one span, correctly scoped, and no downstream role ever proposed `received` for any requirement.

## What it does not guarantee

Span scope constrains what a *quotation* claims. It says nothing about what a *requirement* may claim.
`evidence_class` on an obligation is a separate assertion, and nothing in the span contract stops a
requirement being marked `received` when every span behind it came from a customer message. That is a
different proposition:

> a requirement is satisfied only when a returned artifact establishes it, not when a party reports it

and it is the one the scientific work isolates. The two mechanisms are complementary, at different levels
of the object graph: the type forbids a quote from becoming a fact; the gate forbids a report from
satisfying a requirement.

## How the product is now arranged

| proposition | mechanism | where | enforcement |
|---|---|---|---|
| a quotation is not an established fact | `SourceSpan.scope` literal | `agent_work/contracts.py` | type, unconditional |
| a requirement is not satisfied by a party report | channel gate, per requirement | `agent_work/evidential_channel.py` + `runtime.py` | deterministic, per requirement |
| a document state is not `received` without its own artifact | decoder gate | `evidential_channel_gate_v1.py` + `native_live_workspace_v1.py` | deterministic, per document |

One mechanism per proposition, no proposition guarded twice. The two gates share `evidential_channel`'s
channel typing, so the channel classification exists in exactly one place.

## Evidence, and its limits

- **Decoder surface, measured on the real corpus.** Over all 150 shipped claims the decoder proposes 266
  receipts of which **144 rest only on customer-message pointers**, across 85 of 149 scored claims. The
  gate changes those and leaves the other 122 alone. The rule is not redundant here.
- **Six-role surface, one preserved run.** Zero of ten requirements were capped, because none proposed
  `received`. One run is one run: this establishes that the gate *can* be a no-op on that path, not that it
  always is. A study over many six-role runs was not executed, and the paper says so rather than
  generalizing from a single claim.
- **The requirement-scoping defect is fixed.** The runtime previously offered every span in the run as
  support for any requirement, so one returned artifact anywhere lifted the cap everywhere. It is now
  per requirement and caps when the tie cannot be established. Six regression tests pin it, including the
  case the earlier behaviour got wrong: an unrelated artifact must not admit a party report.
