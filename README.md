# CasePath

### Ask for evidence only when the case requires it.

A plausible checklist can still ask for too much: documents for the wrong kind
of case, or evidence the claimant has already supplied.

CasePath connects each request to the requirement that makes it necessary.
Language-model agents interpret the case; an executable controller determines
the evidence needed. This repository includes the method, two studies, and a
local claims workbench with 150 synthetic cases.

[Read the paper](research/casepath/iclr2027-integrated/dist/casepath_iclr2027_submission.pdf)
· [Explore the method](docs/method-guide.md)
· [Reproduce the results](research/casepath/iclr2027-integrated/README.md)

## From a requirement to a request

> An active requirement needs a fact. Evidence can establish that fact. A
> document is requested only through that connection.

The controller checks applicability, permission to acquire evidence, and what
the available documents establish. Unknown conditions remain questions. Each
request points back to its rule, required fact, and evidence route.

Consider the [guide's invented repair policy](docs/method-guide.md): the cause
of an eligible repair can be established by an inspection report, or by a
service note and a photo together.

| What the case contains | What follows |
| --- | --- |
| The repair is outside the policy's scope | No request under this requirement. |
| Eligibility is unclear | Resolve eligibility first. |
| Evidence is missing and acquisition is allowed | Request the evidence needed by the selected route. |
| A report is present but has not been assessed | Review the report. |
| The note and photo together establish the cause | No additional report is needed. |

The guide contains 45 teaching examples, separate from the studies below.

## What the studies show

**Study A: change one fact in a household-theft case.** On 27 held-out pairs,
the earlier CasePath planner made fewer incorrect checklist changes, with a
recall trade-off. The reference requires 33 additions across these pairs.

| System | Required changes recovered, of 33 | Incorrect additions or withdrawals |
| --- | ---: | ---: |
| CasePath | 24 | 15 |
| Direct | 25 | 27 |
| Graph as context | 31 | 41 |
| Evidence-first | 16 | 52 |

Errors shared by both checklists are invisible to this metric. Computation
differed across methods, and the preregistered accuracy criteria were not met.
[Study details](docs/research-evidence.md) cover uncertainty and how this planner
differs from the newer controller.

**Study B: keep requests within the right tenancy domain.** A retrospective
comparison fixes the model's assessments and changes whether the controller
enforces domain scope, such as rent increase or termination. Both versions
produced outputs for the same 108 cases:

| Requests across the same 108 cases | Without domain scope | With domain scope |
| --- | ---: | ---: |
| All requests | 1,445 | 652 |
| Requests with a valid reference chain | 635 | 635 |
| Requests without a valid reference chain | 810 | 17 |

Scope removes unrelated requests here. These synthetic cases had already been
used in product development. The original full-output evaluation could not bind
reference conditions and accepted none of 1,050 scheduled cells; this later
analysis does not replace that failure. Reference-chain agreement does not
establish legal correctness. The [comparison guide](docs/benchmark-and-baselines.md)
and [reports](research/casepath/iclr2027-integrated/README.md) explain the limits.

## Explore the evidence

| Start here | What you can inspect |
| --- | --- |
| [Study A benchmark](research/casepath/branch-benchmark/README.md) | Cases, predictions, and reference changes. |
| [Reproducibility archive](research/casepath/iclr2027-integrated/dist/casepath_iclr2027_reproducibility.zip) | Inputs, references, outputs, failures, and replay instructions for both studies. |
| [Synthetic intake corpus](docs/INTAKE_PACKET_150.md) | 150 case narratives and 57 attachments: 47 PDFs and 10 images. |
| [Controller](casepath-api/casepath_api/obligation_control/obligation_control_v1.py) and [evidence planner](casepath-api/casepath_api/obligation_control/evidence_demand_v1.py) | The code that determines requests. |

Reproduce Study A from the repository root:

```bash
python3 research/casepath/branch-benchmark/reproduce.py
```

This uses Python's standard library and recorded outputs. No model or network
calls are needed.

## Try the workbench

Read a claim packet, inspect its evidence assessment, and follow its handling
history. The research prototype runs locally in deterministic mode without an
API key. See [local setup](docs/setup.md) for installation.

[License](LICENSE) · [Third-party notices](THIRD_PARTY_NOTICES.md)
