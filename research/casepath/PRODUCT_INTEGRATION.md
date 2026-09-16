# The product runs the paper's method, and this is the receipt

`casepath_api/casepath_process_service_v1.py` composes the same four modules the experiments use — induction, the
case interpreter, the obligation compiler, evidence admission — and defines no reasoning of its own. That is
deliberate: if the service had its own logic, "the product runs the paper's method" would be a claim to audit
rather than a property of the code.

## What one call returns

Run end to end on a real development case (`PRODUCT_TRACE_example.json`), 24 capabilities compiled, 3 document
requests produced. For each request the interface receives the answer to every question a handler actually asks:

| question | field |
|---|---|
| Why is this required? | the process node, and whether it is active or unresolved |
| Why does that node matter? | the authority, its exact text, and its Fedlex URL |
| What fact does it need? | the required fact |
| Why this document? | the evidence capability it establishes |
| When does it stop being required? | the predicate whose resolution closes the node, and its current verdict |

A real request from that run:

> **rent_increase_official_form, registered_mail_receipt**
> node `rent_increase_notified` — *active*
> fact: the tenant was notified of the rent increase
> must show: that the rent-increase notification was provided to the tenant
> authority: **OR Art. 269d Abs. 1** — *"Der Vermieter kann den Mietzins jederzeit auf den nächstmöglichen
> Kündigungstermin erhöhen. Er muss dem Mieter die Mietzinserhöhung mindestens zehn Tage…"*
> source: fedlex.admin.ch/filestore/…/cc/27/317_321_377/20260101/de/xml/…

Every span shown is a verbatim substring of a passage fetched from Fedlex and hashed. Nothing in the chain is
paraphrase.

## Faults are first-class, not hidden

The same run reports 11 clean chains, **11 evidence gaps**, and 2 wrong-branch chains. An evidence gap is a
capability with no route in the document catalogue — the process needs something established and the available
documents cannot establish it. Surfacing that is the point: a system that silently drops what it cannot evidence
looks more competent and serves the handler worse.

## Retraction is an event, not a recomputation

`diff_requests` compares two states and returns what was withdrawn, what was added, which predicates flipped, and
which nodes closed — the audit record shown when a fact arrives and a requirement goes away. Exercised on a real
before/after pair, it correctly reported four added documents and named the three predicates that changed.

## Honest limit

What the product inherits is the method as measured, including its measured weaknesses. On development data the
full compiler withdraws correctly far less often than simply handing the model the graph, and eight of thirteen
nodes in the graph used here carry no obligation at all. The interface will therefore show fewer, better-justified
requests than the reference contract requires, and will sometimes fail to retract one it should. That is the
system's real behaviour and the interface should not paper over it.
