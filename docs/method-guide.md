# Why this document?

A checklist is a consequence of the case state. Before asking for a file,
CasePath determines which obligation applies, whether acquiring more evidence
is permitted, and whether something already held establishes the required fact.

After [starting the local workbench](setup.md), open
**http://127.0.0.1:4173/method.html**. Change the repair's eligibility, acquisition
permission and available evidence. The request and next action change together.
The workbench header links to the same guide under **How it works**.

## Understand one request

The guide uses an invented equipment-repair policy. A qualifying repair requires
evidence of its cause. Either an inspection report or a service note and photo
may establish that fact. New evidence may be acquired only with permission.

| Change in the case | Consequence |
|---|---|
| The repair does not qualify | The obligation is inactive; it generates no request. |
| Eligibility is unresolved | The controller asks to resolve applicability. |
| Evidence is missing and acquisition is permitted | The selected route generates a request with its justification chain. |
| A report is held but not assessed | The controller asks to review it. |
| The note and photo jointly establish the cause | The alternative route is satisfied; no additional report is requested. |
| Each document has been assessed but joint adequacy is unresolved | The controller asks what the documents establish together. |

These are executed semantics on authored teaching inputs, not measured model
accuracy or outcomes on real claims. The full policy, observations, evidence
assessments and controller output are inspectable in the page.

## Inspect the implementation

1. [The example generator](../examples/build_method_guide.py) constructs the
   source rule, obligation and evidence alternatives.
2. [The obligation controller](../casepath-api/casepath_api/obligation_control/obligation_control_v1.py)
   evaluates scope and applicability with true, false and unresolved values.
3. [The evidence planner](../casepath-api/casepath_api/obligation_control/evidence_demand_v1.py)
   checks capability-specific adequacy, selects an alternative, and produces
   requests with scope, obligation, fact, capability, route and source references.
4. [The preserved teaching outputs](../casepath/assets/method-guide-data.json)
   contain all 45 combinations and the hashes of both executed modules.

From the repository root, regenerate or verify the page's data without model
calls or benchmark access:

```bash
.runtime/casepath-dev-v2/venv/bin/python examples/build_method_guide.py
.runtime/casepath-dev-v2/venv/bin/python examples/build_method_guide.py --check
```

The browser selects a preserved deterministic output. It does not approximate
the controller in JavaScript and it does not send a request to a customer.

## Read the evidence correctly

Document recall rewards finding required items, but does not penalize requesting
everything. Evaluate coverage together with unjustified demand. The native
comparison additionally measures valid justification chains, branch-sensitive
errors, evidence-obligation completeness and source support. Their denominators
and semantics are specified in the evaluator, not inferred from this guide.

The study's source representation is compiled deterministically from shared
public templates. It does not test learned graph induction. Its obligation
controller determines requests; an explanatory macro-process diagram is not the
online acquisition controller.

The workbench's handling journal has separate admission rules. Displaying a
controller plan does not make its evidence accepted, its action executed, or its
output a verified legal decision. Recorded benchmark replay and live inference
must be labeled separately wherever they are exposed.
